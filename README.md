# cloud-nonce-discoverer

## Deployment

### Prerequisites

-  AWS account
- `Python 3.7+`
- `boto3`
- `awscli`
- `jsonmerge`

### Setup

1. Create a user at https://console.aws.amazon.com/iam/home?region=us-west-1#/users with AdministratorAccess
    - Enter your credentials in `~/.aws/credentials`
2. Create roles at https://console.aws.amazon.com/iam/home?region=us-west-1#/roles for the following:
    - AmazonEC2FullAccess
    - AmazonEC2RoleforSSM
    - AWSLambdaFullAccess
    - AmazonSSMFullAccess
    - AWSLambdaSQSQueueExecutionRole
    - CloudwatchApplicationInsightsServiceLinkedRolePolicy
3. Create an S3 bucket. Provide the name of the bucket as input at the start of the program
4. Create 3 SQS queues named: 'in_queue', 'out_queue', 'scram_queue'
5. Create a Lambda function using the code in [on_input.py](./lambda/run_script.py)
    - Map the queue 'in_queue' to this Lambda function
6. Run `python client.py -i {number of instances} -d {difficulty} -t {timeout}`

### Deployment

To run using direct specification of number of instances:

```
python client.py -i {number of instances} -d {difficulty} -t {timeout}
```

To run using indirect specification determining the number of instances from the runtime provided:

```
python client.py -i {number of instances} -d {difficulty} -c
>>> Enter your confidence value: 0.95
>>> Enter your desired runtime: 4.5
>>> Would you like to use the minimum number of instances possible? y/n : n
```

Note: The effectiveness of indirect specfication will vary depending on how many times the program has been previously run, as it makes use of historical log data in order to make a well-informed decision.

### Arguments

- `instances -i`  : The number of EC2 instances to divide the task across.
- `difficulty -d` : The difficulty of nonce discovery. This corresponds to the number of leading zero bits required in the hash.
- `timeout -t`    : Limit of time in seconds before scram is initiated.
- `logscram -l`   : Gives the option to collect logs from instances on the event of a scram.
- `confidence -c` : This will allow the program to automatically choose the number of instances to spawn according to runtime.


## Objective

A Proof-of-Work (PoW) system is a consensus mechanism commonly used by blockchains in order to verify incoming blocks. For every  block holding unconfirmed transactions, a random 32-bit number is appended to it, which is known as the ‘nonce’. This block of data is then hashed using SHA-256 twice (aka SHA-256 squared). The objective of PoW is to find the ‘golden nonce’. This refers to the value of the nonce for which the hashed block has a number *n* or more consecutive leading zero bits. The number of zero bits required is known as the difficulty, D. Once the golden nonce is found, this culminates the end of the PoW process, verifying and adding the block to the blockchain. 

With the search space to find the golden nonce being a number between 0 and 2^32, an increasing difficulty leads to a runtime growing exponentially as 2^N. It is possible to split this search space in order to parallelise the task. The aim of this system is to use cloud infrastructure, in this case AWS, in order to reduce the runtime of discovering the golden nonce.


