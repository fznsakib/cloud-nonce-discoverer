import os
import time

# Start taking logs from 19:00:00 3/12/2019

difficulties = [1, 2, 4, 8, 16, 24, 28]
repeats = 10

# for difficulty in difficulties:
for instance in range(1, 13):
    for i in range(0, repeats):
        os.system(f'python client.py -d {24} -i {instance}')
        time.sleep(5)