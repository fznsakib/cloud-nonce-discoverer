import json
import boto3
import time

ec2 = boto3.resource('ec2')
ssm = boto3.client('ssm')

def lambda_handler(event, context):
    
    message_body = json.loads(event['Records'][0]['body'])
    
    # Get instance_id to run script on
    instance_id = message_body['instanceId']

    # Get parameters to run for pow.py
    difficulty = message_body['difficulty']
    start_nonce = message_body['startNonce']
    end_nonce = message_body['endNonce']
    date_time = message_body['dateTime']
    log_on_scram = message_body['logOnScram']
    bucket_name = message_body['bucketName']

    command_download_script = f'aws s3 cp s3://{bucket_name}/pow.py home/ec2-user/pow.py'
    command_run_script = f'sudo python3 home/ec2-user/pow.py --start {start_nonce} --end {end_nonce} --difficulty {difficulty} --id {instance_id} --datetime {date_time}'
    
    commands = [command_download_script, command_run_script]

    # Send command to download and then execute script on instance
    ssmresponse = ssm.send_command(
        InstanceIds=[instance_id], 
        DocumentName='AWS-RunShellScript',
        Parameters= { 'commands': commands },
        CloudWatchOutputConfig={
            'CloudWatchLogGroupName': 'run_command_test',
            'CloudWatchOutputEnabled': True
        }
    )
    
    return {
        'statusCode': 200
    }
