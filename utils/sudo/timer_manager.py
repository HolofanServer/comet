import asyncio

class TimerManager:
    def __init__(self):
        self.timers = {}

    async def start_timer(self, user_id, session_id, delay, callback):
        if user_id in self.timers:
            self.cancel_timer(user_id)

        task = asyncio.create_task(self._timer_task(user_id, session_id, delay, callback))
        self.timers[user_id] = task

    async def _timer_task(self, user_id, session_id, delay, callback):
        try:
            await asyncio.sleep(delay)
            await callback(session_id)
        except asyncio.CancelledError:
            pass

    def cancel_timer(self, user_id):
        if user_id in self.timers:
            self.timers[user_id].cancel()
            del self.timers[user_id]
