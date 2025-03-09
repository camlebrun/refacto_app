import random
import datetime
import pandas as pd

def generate_fake_log(num_entries=100):
    logs = []
    start_time = datetime.datetime(2023, 1, 1)

    for _ in range(num_entries):
        timestamp = start_time + datetime.timedelta(days=random.randint(0, 365), hours=random.randint(0, 23), minutes=random.randint(0, 59))
        data_scanned = random.randint(100, 10000)  # in MB
        is_incremental = random.choice([True, False])
        logs.append({
            'timestamp': timestamp,
            'data_scanned': data_scanned,
            'is_incremental': is_incremental
        })

    return pd.DataFrame(logs)

# Generate fake log data
fake_log = generate_fake_log()
print(fake_log)
