# cloud-nonce-discoverer

## Introduction

A Proof-of-Work (PoW) system is a consensus mechanism commonly used by blockchains in order to verify incoming blocks. For every  block holding unconfirmed transactions, a random 32-bit number is appended to it, which is known as the ‘nonce’. This block of data is then hashed using SHA-256 twice (aka SHA-256 squared). The objective of PoW is to find the ‘golden nonce’. This refers to the value of the nonce for which the hashed block has a number *n* or more consecutive leading zero bits. The number of zero bits required is known as the difficulty, D. Once the golden nonce is found, this culminates the end of the PoW process, verifying and adding the block to the blockchain. 

With the search space to find the golden nonce being a number between 0 and 2^32, an increasing difficulty leads to a runtime growing exponentially as 2^N. It is possible to split this search space in order to parallelise the task. The aim of this system is to use cloud infrastructure, in this case AWS, in order to reduce the runtime of discovering the golden nonce.

# Deployment



## Prerequisites

- `Python 3.7+`
- `boto3`
- `awscli`
- `jsonmerge`

## Arguments

- `instances -i`  : The number of EC2 instances to divide the task across.
- `difficulty -d` : The difficulty of nonce discovery. This corresponds to the number of leading zero bits required in the hash.
- `timeout -t`    : Limit of time in seconds before scram is initiated.
- `logscram -l`   : Gives the option to collect logs from instances on the event of a scram.
- `confidence -c` : This will allow the program to automatically choose the number of instances to spawn according to runtime.

