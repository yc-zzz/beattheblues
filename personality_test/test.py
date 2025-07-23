from reset_time import UserTable

example = UserTable()

def update_table_test():
    import pandas as pd
    from datetime import date
    df = [{'id': 1, 'request_date': date(2025, 7, 21), 'description': 'yabadabadoo'}, 
        {'id': 2, 'request_date': date(2025, 7, 21), 'description': 'yabadabadoo'}]
    df = pd.DataFrame(df)
    print(example.refresh())

