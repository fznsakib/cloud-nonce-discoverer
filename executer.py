import os
import time

# Start taking logs from 19:00:00 3/12/2019

# difficulties = [1, 2, 4, 8, 16, 24, 28]
difficulties = [24]
repeats = 1
instances = [8, 4, 2, 1]

# for difficulty in difficulties:
#     for instance in range(12, 13):
#         for i in range(0, repeats):
#             os.system(f'python client.py -d {difficulty} -i {instance}')
#             time.sleep(5)
            
for instance in instances:
    for i in range(0, repeats):
        os.system(f'python client.py -d {28} -i {instance}')
        time.sleep(5)