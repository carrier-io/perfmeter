package jmeter.backend.listener;

import jmeter.backend.listener.outputs.config.InfluxDBConfig;
import org.apache.commons.lang3.exception.ExceptionUtils;
import org.apache.jmeter.assertions.AssertionResult;
import org.apache.jmeter.config.Arguments;
import org.apache.jmeter.control.TransactionController;
import org.apache.jmeter.protocol.http.sampler.HTTPSampleResult;
import org.apache.jmeter.samplers.SampleResult;
import org.apache.jmeter.threads.JMeterContextService;
import org.apache.jmeter.visualizers.SamplingStatCalculator;
import org.apache.jmeter.visualizers.backend.AbstractBackendListenerClient;
import org.apache.jmeter.visualizers.backend.BackendListenerContext;
import org.apache.jorphan.logging.LoggingManager;
import org.influxdb.InfluxDB;
import org.influxdb.InfluxDBFactory;
import org.influxdb.dto.Point;
import org.influxdb.dto.Point.Builder;

import java.io.FileWriter;
import java.io.IOException;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;


public class InfluxBackendListenerClient extends AbstractBackendListenerClient implements Runnable {

	private static final String delimeter = "\t";
	private static final org.apache.log.Logger LOGGER = LoggingManager.getLoggerForClass(); // Logger
	private static final String KEY_PROJECT_NAME = "projectName";
	private static final String KEY_TEST_TYPE = "testType";
	private static final String KEY_ENV_TYPE = "envType";
	private static final String KEY_BUILD = "buildID";
	private static final String KEY_LG_NAME = "loadGenerator";
	private static final String KEY_SIMULATION = "simulation";
	private static final String KEY_PERIODICITY = "periodicity";
	private static final String KEY_PERIODICITY_COMMENT = "periodicity_comment";

	private static final String KEY_USE_REGEX_FOR_SAMPLER_LIST = "useRegexForSamplerList";
	private static final String KEY_SAMPLERS_LIST = "samplersList";
	private static final String KEY_CREATE_AGGREGATED_REPORT = "createAggregatedReport";


	/**
	 * +++++++++++++++++++++++++++++++++++++++++++++++++++++
	 * +++++++++INFLUXDB Parameter Keys Block Start+++++++++
	 * +++++++++++++++++++++++++++++++++++++++++++++++++++++
	 */
	private long testStart;
	private int testDuration;

	HashMap<String, String> tagsGlobal = new HashMap();
	HashMap<String, String> tagsVUsers = new HashMap();
	HashMap<String, String> tagsSamples = new HashMap();
	private static final String SEPARATOR = ";";
	private static final int ONE_MS_IN_NANOSECONDS = 1000000;
	private ScheduledExecutorService scheduler;

	private String testType; // Test type.
	private String envType; // Test type.
	private String projectName; // Project name
	private String loadGenerator; // Load Generator name
	private String buildId;
	private String simulation;
	private String periodicity;
	private String periodicityComment;

	private String samplersList = "";
	private String regexForSamplerList;
	private Set<String> samplersToFilter;
	InfluxDBConfig influxDBConfig; // InfluxDB configuration.
	private InfluxDB influxDB; // influxDB client.
	private Random randomNumberGenerator;
	private boolean isInfluxDBPingOk;
	private final Map<String, SamplingStatCalculator> tableRows = new ConcurrentHashMap();


	public void run() {
		try {
			JMeterContextService.ThreadCounts tc = JMeterContextService.getThreadCounts();
			this.addVirtualUsersMetrics(this.getUserMetrics().getMinActiveThreads(), this.getUserMetrics().getMeanActiveThreads(), this.getUserMetrics().getMaxActiveThreads(), tc.startedThreads, tc.finishedThreads);
		} catch (Exception var2) {
			LOGGER.error("Failed writing to InfluxDB", var2);
		}
	}

	private void addVirtualUsersMetrics(int minActiveThreads, int meanActiveThreads, int maxActiveThreads, int startedThreads, int finishedThreads) {
		Builder builder = Point.measurement("users").time(System.currentTimeMillis(), TimeUnit.MILLISECONDS);
		builder.addField("active", (long)startedThreads - (long) finishedThreads);
		builder.addField("waiting", 0);
		builder.addField("done", (long)finishedThreads);
		builder.addField("user_count", (long)startedThreads);
		builder.addField("env", this.envType);
		builder.tag("test_type", this.testType);
		builder.tag("build_id", this.buildId);
		builder.tag("lg_id", this.loadGenerator);
		builder.tag("simulation", this.simulation);
		builder = this.addTags(builder, this.tagsGlobal);
		builder = this.addTags(builder, this.tagsVUsers);
		this.influxDB.write(this.influxDBConfig.getInfluxDatabase(), this.influxDBConfig.getInfluxRetentionPolicy(), builder.build());
	}

	public void handleSampleResults(List<SampleResult> sampleResults, BackendListenerContext context) {
		Iterator sampleResultIterator = sampleResults.iterator();
		context.getParameterNamesIterator();

		try {
			writeToFile(sampleResults);
		} catch (IOException e) {
			e.printStackTrace();
		}

		while(true) {
			SampleResult sampleResult;
			String httpMethod;
			String sampler_type;
			boolean isSuccessful;
			long currentTime;
			do {
				do {
					if (!sampleResultIterator.hasNext()) {
						return;
					}
					sampleResult = (SampleResult) sampleResultIterator.next();
					if (sampleResult instanceof HTTPSampleResult) {
						HTTPSampleResult http_sample = (HTTPSampleResult) sampleResult;
						httpMethod = http_sample.getHTTPMethod();
						sampler_type = "REQUEST";
					} else {
						httpMethod = "TRANSACTION";
						sampler_type = "TRANSACTION";
					}
					this.getUserMetrics().add(sampleResult);
				} while((null == this.regexForSamplerList || !sampleResult.getSampleLabel().matches(this.regexForSamplerList)) && !this.samplersToFilter.contains(sampleResult.getSampleLabel()));

				SamplingStatCalculator calc = (SamplingStatCalculator)this.tableRows.computeIfAbsent(sampleResult.getSampleLabel(), (label) -> {
					SamplingStatCalculator newRow = new SamplingStatCalculator(label);
					return newRow;
				});
				synchronized(calc) {
					calc.addSample(sampleResult);
				}

				isSuccessful = sampleResult.isSuccessful();
				currentTime = System.currentTimeMillis();
				String responseCode = sampleResult.getResponseCode();
				if (responseCode.length()>3 || responseCode.length()==0){
					responseCode = "NuN";
				}
				double tps_rate = (double)Math.round(calc.getRate() * 1000.0D) / 1000.0D;
				double kbytes_per_second = (((long)sampleResult.getBytes() + (long)sampleResult.getSentBytes()) / (sampleResult.getTime() * 1024.0D)) * 1000;
				double networkRate = (double)Math.round(kbytes_per_second * 1000.0D) / 1000.0D;
				long hit = (long)((currentTime - sampleResult.getTime())/1000);
				if (!sampleResult.getSampleLabel().startsWith("Util_")) {
				    Builder builder = Point.measurement(this.simulation)
						    .time(currentTime, TimeUnit.MILLISECONDS)
						    .addField("connect_time", sampleResult.getConnectTime())
						    .addField("latency", sampleResult.getLatency())
						    .addField("hit", hit)
						    .addField("response_time", sampleResult.getTime())
						    .addField("errorCount", (long)sampleResult.getErrorCount())
						    .addField("status", isSuccessful ? "OK" : "KO")
						    .addField("status_code", responseCode)
						    .addField("tpsRate", tps_rate)
						    .addField("networkRate", networkRate)
						    .tag("user_id", sampleResult.getThreadName())
						    .tag("method", httpMethod)
						    .tag("sampler_type", sampler_type)
						    .tag("request_name", sampleResult.getSampleLabel())
						    .tag("env", this.envType)
						    .tag("test_type", this.testType)
						    .tag("build_id", this.buildId)
						    .tag("lg_id", this.loadGenerator)
						    .tag("simulation", this.simulation);
				    builder = this.addTags(builder, this.tagsGlobal);
				    builder = this.addTags(builder, this.tagsSamples);
				    this.influxDB.write(this.influxDBConfig.getInfluxDatabase(), this.influxDBConfig.getInfluxRetentionPolicy(), builder.build());
				}
			} while(isSuccessful);
		}
	}

	private void writeToFile(List<SampleResult> sampleResults) throws IOException {
		Iterator sampleResultIterator = sampleResults.iterator();
		FileWriter fileWriter = new FileWriter("/tmp/" + this.simulation + ".log", true);
		SampleResult sampleResult;

		String httpMethod;
		String query = "[";
		do {
			try {
				sampleResult = (SampleResult) sampleResultIterator.next();
				if (!sampleResult.isSuccessful()) {
					if (sampleResult instanceof HTTPSampleResult) {
						HTTPSampleResult http_sample = (HTTPSampleResult) sampleResult;
						httpMethod = http_sample.getHTTPMethod();
						query += http_sample.getQueryString();
					} else {
						httpMethod = "TRANSACTION";
					}
					String requestName = sampleResult.getSampleLabel();
					String responseMessage = sampleResult.getResponseMessage();
					String responseCode = sampleResult.getResponseCode();
					if (responseCode.length()>3 || responseCode.length()==0){
						responseCode = "NuN";
					}
					String response = sampleResult.getResponseDataAsString().replaceAll("\t", " ")
							.replaceAll("\n"," ").replaceAll("\"","")
							.replaceAll("\'","").replaceAll("'","");

					String headers = sampleResult.getRequestHeaders().replaceAll("\t", " ")
							.replaceAll("\n"," ");
					if (response.length() == 0) {
						response = "[]";
					}
					if (headers.length() == 0) {
						headers = "[]";
					}
					String errorMessage = "[";
					for (AssertionResult result : sampleResult.getAssertionResults()) {
						if (result.isFailure()) {
							errorMessage += result.getFailureMessage().replaceAll("\n", " ")
									.replaceAll("\t", " ");
							break;
						}
					}
					errorMessage += "]";
					query += "]";
					String error_key = requestName+"_"+httpMethod+"_"+responseCode;
					fileWriter.write(new StringBuilder()
							.append("Error key: ").append(error_key).append(delimeter)
							.append("Request name: ").append(requestName).append(delimeter)
							.append("Method: ").append(httpMethod).append(delimeter)
							.append("Response code: ").append(responseCode).append(delimeter)
							.append("URL: ").append(sampleResult.getUrlAsString()).append(delimeter)
							.append("Error message: ").append(errorMessage).append(delimeter)
							.append("Request params: ").append(query).append(delimeter)
							.append("Headers: ").append(headers).append(delimeter)
							.append("Response body: ").append(response).append(responseMessage).append(delimeter)
							.append("\n").toString());
				}

			} catch(Exception e) {
				e.printStackTrace();
			}


		}
		while (sampleResultIterator.hasNext());
		fileWriter.close();
	}

	private void parseCustomTags(BackendListenerContext context) {
		Iterator iter = context.getParameterNamesIterator();

		while(iter.hasNext()) {
			String param = (String)iter.next();
			if (param.startsWith("tag.")) {
				String[] parts = param.split("\\.");
				String value = context.getParameter(param, "");
				String measurement_or_key = parts[1].toLowerCase();
				if (value.length() > 0) {
					if (parts.length > 2) {
						String key = parts[2];
						byte var9 = -1;
						switch(measurement_or_key.hashCode()) {
							case -805148846:
								if (measurement_or_key.equals("vusers")) {
									var9 = 0;
								}
								break;
							case 1864843273:
								if (measurement_or_key.equals("samples")) {
									var9 = 1;
								}
						}

						switch(var9) {
							case 0:
								this.tagsVUsers.put(key, value);
								break;
							case 1:
								this.tagsSamples.put(key, value);
						}
					} else {
						this.tagsGlobal.put(measurement_or_key, value);
					}
				}
			}
		}

		LOGGER.info("Custom Global tags: " + this.tagsGlobal);
		LOGGER.info("Custom VUsers tags: " + this.tagsVUsers);
		LOGGER.info("Custom Samples tags: " + this.tagsSamples);
	}

	public Builder addTags(Builder point, Map<String, String> tags) {
		Iterator var3 = tags.entrySet().iterator();

		while(var3.hasNext()) {
			Map.Entry<String, String> entry = (Map.Entry)var3.next();
			point.tag((String)entry.getKey(), (String)entry.getValue());
		}

		return point;
	}

	@Override
	public Arguments getDefaultParameters() {
		Arguments arguments = new Arguments();
		arguments.addArgument(KEY_SIMULATION, "${__P(test_name,test)}");
		arguments.addArgument(KEY_ENV_TYPE, "${__P(env.type,demo)}");
		arguments.addArgument(KEY_TEST_TYPE, "${__P(test.type,demo)}");
		arguments.addArgument(KEY_LG_NAME, "${__P(lg.id,${__machineName()})}");
		arguments.addArgument(KEY_BUILD, "${__P(build.id,1)}");
		arguments.addArgument(KEY_PERIODICITY, "${__P(periodicity, debug)}");
		arguments.addArgument(KEY_PERIODICITY_COMMENT, "${__P(periodicity_comment, test_comment)}");
		arguments.addArgument(InfluxDBConfig.KEY_INFLUX_DB_HOST, "${__P(influx.host,127.0.0.1)}");
		arguments.addArgument(InfluxDBConfig.KEY_INFLUX_DB_PORT, "${__P(influx.port,8086)}");
		arguments.addArgument(InfluxDBConfig.KEY_INFLUX_DB_USER, "${__P(influx.username,db_username)}");
		arguments.addArgument(InfluxDBConfig.KEY_INFLUX_DB_PASSWORD, "${__P(influx.password,)}");
		arguments.addArgument(InfluxDBConfig.KEY_INFLUX_DB_DATABASE, "${__P(influx.db,jmeter)}");
		arguments.addArgument(InfluxDBConfig.KEY_RETENTION_POLICY, "${__P(influx.retention.policy,autogen)}");
		arguments.addArgument("samplersList", ".*");
		arguments.addArgument("useRegexForSamplerList", "true");

		return arguments;
	}

	public Builder addGlobalTags(Builder point, Map<String, String> tags){
		Iterator var2 = tags.entrySet().iterator();

		while(var2.hasNext()) {
			Map.Entry<String, String> entry = (Map.Entry)var2.next();
			point.tag(entry.getKey(), entry.getValue());
		}

		return point;
	}

	@Override
	public void setupTest(BackendListenerContext context) throws Exception {
		testType = context.getParameter(KEY_TEST_TYPE, "${__P(test.type,demo)}");
		envType = context.getParameter(KEY_ENV_TYPE, "${__P(env.type,demo)}");
		projectName = context.getParameter(KEY_PROJECT_NAME, "${__P(project.id,demo)}");
		loadGenerator = context.getParameter(KEY_LG_NAME, "${__P(lg.id,load_generator");
		buildId = context.getParameter(KEY_BUILD, "${__P(build.id,1)}");
		simulation = context.getParameter(KEY_SIMULATION, "${__P(SIMULATION,test)}");
		periodicity = context.getParameter(KEY_PERIODICITY, "debug");
		periodicityComment = context.getParameter(KEY_PERIODICITY_COMMENT, "test_comment");

		parseCustomTags(context);
		setupInfluxClient(context);
		scheduler = Executors.newScheduledThreadPool(1);
		scheduler.scheduleAtFixedRate(this,1L,1L,TimeUnit.SECONDS);
		parseSamplers(context);
	}

	@Override
	public void teardownTest(BackendListenerContext context) throws Exception {
		LOGGER.info("Shutting down scheduler...");
		this.scheduler.shutdown();
		this.influxDB.disableBatch();

		try {
			this.scheduler.awaitTermination(30L, TimeUnit.SECONDS);
			LOGGER.info("Scheduler has been terminated!");
		} catch (InterruptedException var3) {
			LOGGER.error("Error waiting for end of scheduler");
		}

		this.samplersToFilter.clear();
		super.teardownTest(context);
	}

	/**
	 * Setup influxDB client.
	 *
	 * @param context
	 *            {@link BackendListenerContext}.
	 */
	private void setupInfluxClient(BackendListenerContext context) {
		try {
			influxDBConfig = new InfluxDBConfig(context);
			influxDB = InfluxDBFactory.connect(influxDBConfig.getInfluxDBURL(), influxDBConfig.getInfluxUser(), influxDBConfig.getInfluxPassword());
			influxDB.enableBatch(100, 5, TimeUnit.SECONDS);
			createDatabaseIfNotExistent();
			isInfluxDBPingOk = true;
			LOGGER.info("++++++ InfluxDB ping test: Success ++++++");
		} catch (RuntimeException e){
			isInfluxDBPingOk = false;
			LOGGER.error("------InfluxDB ping test: Failed------");
			LOGGER.info(ExceptionUtils.getStackTrace(e));
		}
	}

	private void parseSamplers(BackendListenerContext context) {
		this.samplersList = context.getParameter("samplersList", "");
		this.samplersToFilter = new HashSet();
		if (context.getBooleanParameter("useRegexForSamplerList", false)) {
			this.regexForSamplerList = this.samplersList;
		} else {
			this.regexForSamplerList = null;
			String[] samplers = this.samplersList.split(";");
			this.samplersToFilter = new HashSet();
			String[] var3 = samplers;
			int var4 = samplers.length;

			for(int var5 = 0; var5 < var4; ++var5) {
				String samplerName = var3[var5];
				this.samplersToFilter.add(samplerName);
			}
		}
	}

	/**
	 * Creates the configured database in influxdb if it does not exist yet.
	 */
	private void createDatabaseIfNotExistent() {
		List<String> dbNames = influxDB.describeDatabases();
		if (!dbNames.contains(influxDBConfig.getInfluxDatabase())) {
			influxDB.createDatabase(influxDBConfig.getInfluxDatabase());
		}
	}
}