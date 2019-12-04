import boto3
import awslib
import time

logs = boto3.client('logs')

def getLogStats(field, difficulty, noOfInstances):

    response = logs.start_query(
        logGroupName='PoW_logs',
        startTime=0,
        endTime=int(time.time()),
        queryString=(
            f'fields {field}' +
            f'| filter difficulty == {difficulty} and noOfInstances == {noOfInstances} and success == 1' +
            f'| stats count({field}) as count, avg({field}) as mean, stddev({field}) as sd')
    )
    
    query_id = response['queryId']
    
    # Keep trying to get query until it has completed running
    while True:
        response = logs.get_query_results(
            queryId=query_id
        )
        if response['status'] == 'Complete':
            break
    
    stats = {}
    for result in response['results'][0]:
        stats[result['field']] = float(result['value'])
    
    return stats
