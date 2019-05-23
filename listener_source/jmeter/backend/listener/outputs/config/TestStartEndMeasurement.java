package jmeter.backend.listener.outputs.config;

/**
 * Constants (Tag, Field, Measurement) names for the measurement that denotes start and end points of a load test.
 * 
 */
public interface TestStartEndMeasurement {

	String MEASUREMENT_NAME = "reportEvent"; // Measurement name

	 interface Tags {
		String TYPE = "status"; // Start or End type tag.
	}
	 interface Fields {
		String DURATION = "duration";
		String ENVIRONMENT = "environment";
		String SIMULATION = "simulation";
		String TEST_TYPE = "testType";
		String TEXT = "text";
		String TITLE = "title"; 
		String USER_COUNT = "userCount"; 
	}
	 interface Values {
		String FINISHED = "Test finished";
		String STARTED = "Test started";
	}
}
