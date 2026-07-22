from datetime import datetime, timedelta

def get_last_fr():
    today = datetime.now()
    # weekday returns = fr 4 mon 0 sun 6
    days_since_fr = (today.weekday() - 4) % 7
    
    #if today fr back to prev fr
    if days_since_fr == 0: days_since_fr = 7
        
    last_fr = today - timedelta(days=days_since_fr)
    return last_fr.strftime("%Y-%m-%d")
