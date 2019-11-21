import boto3
import sys
import cnd

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
Initialise boto3 interface to AWS
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''
s3 = boto3.resource('s3')
sqs = boto3.client('sqs')
queue_name = 'queue.fifo'

# Upload python script to S3 bucket
BUCKET = "faizaanbucket"
s3.Bucket(BUCKET).upload_file("cnd.py", "cnd.py")

# Create an SQS queue
response = sqs.create_queue(
    QueueName=queue_name,
    Attributes={
        'DelaySeconds': '60',
        'MessageRetentionPeriod': '86400',
        'FifoQueue': 'true',
        'ContentBasedDeduplication': 'true',
    }
)

response = sqs.get_queue_url(QueueName=queue_name)
queue_url = response['QueueUrl']

response = sqs.send_message(
    QueueUrl=queue_url,
    MessageAttributes={
        'Title': {
            'DataType': 'String',
            'StringValue': 'The Whistler'
        },
        'Author': {
            'DataType': 'String',
            'StringValue': 'John Grisham'
        },
        'WeeksOn': {
            'DataType': 'Number',
            'StringValue': '6'
        }
    },
    MessageBody=(
        'Information about current NY Times fiction bestseller for week of 12/11/2016.'
    ),
    MessageGroupId='0',
)

print(response)


# Delete the SQS queue
sqs.delete_queue(QueueUrl=queue_url)


# ec2 = boto3.client('ec2')
# response = ec2.describe_instances()
# print(response)

# ec2 = boto3.client('ec2')
# if sys.argv[1] == 'ON':
#     response = ec2.monitor_instances(InstanceIds=['i-023089b4036160ad8'])
# else:
#     response = ec2.unmonitor_instances(InstanceIds=['i-023089b4036160ad8'])
# print(response)