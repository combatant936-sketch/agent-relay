from database import db_session, Agent, Task, Attempt
with db_session() as db:
    agents = db.query(Agent).all()
    print(f'=== AGENTS ({len(agents)}) ===')
    for a in agents:
        print(f'  {a.name}  {a.id}')
    tasks = db.query(Task).all()
    print(f'=== TASKS ({len(tasks)}) ===')
    for t in tasks:
        print(f'  {t.id}  status={t.status}  from={t.sender_id}  to={t.recipient_id}')
    attempts = db.query(Attempt).all()
    print(f'=== ATTEMPTS ({len(attempts)}) ===')
    for at in attempts:
        print(f'  {at.task_id}  attempt={at.attempt_number}  outcome={at.outcome}')
