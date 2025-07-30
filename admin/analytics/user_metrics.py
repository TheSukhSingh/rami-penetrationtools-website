from auth.models import LoginEvent
from datetime import datetime, timedelta


def signups_over_time(days=30):
    # returns list of (date, count)
    data = []
    today = datetime.utcnow().date()
    for i in range(days):
        day = today - timedelta(days=i)
        count = LoginEvent.query.filter(
            LoginEvent.timestamp.between(
                day, day + timedelta(days=1)
            )
        ).count()
        data.append({'date': day.isoformat(), 'logins': count})
    return list(reversed(data))