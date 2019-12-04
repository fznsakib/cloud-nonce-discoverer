import math
import time
import boto3
import scipy.stats as st
import pprint
import awslib
import logstats

logs = boto3.client('logs')


def getInstanceConfidenceRanges(difficulty, confidence):
    instanceConfidenceRanges = {}
    max_no_of_instances = 12

    # Calculate confidence range from sample for difficulty for each instance
    for i in range(1, max_no_of_instances + 1):
        # Get count, mean and standard deviation of sample
        stats = logstats.getLogStats('searchTime', difficulty, i)

        # Since scipy returns Z-score from the p-value given to the absolute
        # left, it needs to be returned in a way that instead gives the
        # Z-score symmetrical around the mean 0. This is done by halving
        # (1 - confidence) so that the upper end of the distribution is ignored.
        # z_score = float(st.norm.ppf(1 - (1 - confidence)/2))
        upper_z_score = float(st.norm.ppf(confidence))

        # The 8–95–99.7 rule says all values (99.7 ~= 100%)in a normal distribution
        # lies within 3 standard deviations of the mean
        lower_z_score = 3

        # Calculate standard error
        err = stats['sd']/math.sqrt(stats['count'])

        lower_limit = stats['mean'] - lower_z_score * err

        # Bound lower limit with negative values
        if lower_limit < 0:
            lower_limit = 0

        upper_limit = stats['mean'] + upper_z_score * err

        instanceConfidenceRanges[i] = {
            'lower_limit': lower_limit,
            'mean': stats['mean'],
            'upper_limit': upper_limit
        }

        if (i < max_no_of_instances):
            print(
                f'Calculated confidence range for ({i}/12) no of instances', end="\r")
        else:
            print(f'Calculated confidence range for ({i}/12) no of instances')

    return instanceConfidenceRanges


def getNoOfInstancesByRuntime(runtime, difficulty, confidence, minimise_instances):
    instanceConfidenceRanges = getInstanceConfidenceRanges(
        difficulty, confidence)

    viable_no_of_instances = {}
    lowest_no_of_instances = len(instanceConfidenceRanges) + 1
    
    # Go through limits to see which fall under runtime
    # If minimum instances requested, then simply keep a track on the
    # lowest number of instances that has an upper limit which is less than
    # the runtime
    for i, confidenceRange in enumerate(instanceConfidenceRanges.values()):
        if confidenceRange['upper_limit'] < runtime:
            viable_no_of_instances[i + 1] = confidenceRange['upper_limit']
            if (i + 1) < lowest_no_of_instances:
                lowest_no_of_instances = i + 1
	 
    if lowest_no_of_instances == (len(instanceConfidenceRanges) + 1):
        return -1
	
 # Return lowest number of instances which fall under the runtime if requested
    if minimise_instances:
        return lowest_no_of_instances

    # Find no of instances which will give a number closest to the runtime
    no_of_instances = len(instanceConfidenceRanges)
    smallest_diff = runtime

    for num, upper_limit in viable_no_of_instances.items():
        diff = runtime - upper_limit
        if diff < smallest_diff:
            smallest_diff = diff
            no_of_instances = num

    return no_of_instances
