#!/usr/bin/env python

import heapq, unittest

DEFAULT_PRIORITY = 10   # priority only affects order of simulatneously scheduled events

class SimEvent(object):
  def __init__(self, process, value=None, t_abs=None, recurrence=None, priority=DEFAULT_PRIORITY):
    super(SimEvent,self).__init__()
    assert isinstance(process, Process)
    self.process = process
    self._value = value
    self.t_abs = t_abs
    self.recurrence = recurrence
    self._priority = priority
  def __cmp__(self, other):
    return cmp((self.t_abs, self._priority), (other.t_abs, other._priority))
  def Exec(self):
    self.process.Exec(self._value)

class TestEvent(unittest.TestCase):
  def testEvent(self):
    p = Process(Scheduler(), lambda:None)
    self.assertTrue(SimEvent(p,t_abs=3) <  SimEvent(p,t_abs=4))
    self.assertTrue(SimEvent(p,t_abs=4) == SimEvent(p,t_abs=4))
    self.assertTrue(SimEvent(p,t_abs=4) >  SimEvent(p,t_abs=3))
    self.assertTrue(SimEvent(p,t_abs=3,priority=1) <  SimEvent(p,t_abs=3))
    self.assertTrue(SimEvent(p,t_abs=4,priority=1) >  SimEvent(p,t_abs=3))

class Process(object):
  '''A process is a function that accepts inputs.
    The process function is called with an event's value when the time for that event arrives.
    A count of pending events is maintained.
    PostInput creates an event with an immediate timestamp.
    PostEvent creates an event some time in the future.
  '''
  # The scheduler manages the events and this Process' eventCount
  def __init__(self, aScheduler, aCallable):
    super(Process, self).__init__()
    # aCallable could theoretically be a class (constructor), but that's probably an error.
    assert callable(aCallable) and not isinstance(aCallable, type)
    self._scheduler = aScheduler
    self._target = aCallable
    self.eventCount = 0
  def PostInput(self, value, priority=DEFAULT_PRIORITY):
    self._scheduler.PostEvent(self, value, priority=priority)
  def PostEvent(self, value=None, dt=0, recurring=False, priority=DEFAULT_PRIORITY):
    self._scheduler.PostEvent(self, value, dt=dt, recurring=recurring, priority=priority)
  def isInputAvailable(self):
    return self.eventCount > 0
  def Exec(self, *posargs, **kwargs):
    return self._target(*posargs, **kwargs)

class Scheduler(object):
  def __init__(self):
    super(Scheduler,self).__init__()
    # Each entry is of the form: (expirationTimeAbs, priority, recurrenceTimeRelative, receiverObj, posArgs, kwArgs)
    self._clock = 0L
    self._eventQueue = []       # managed with heapq
    self._processes = set()

  def CreateProcess(self, aCallable):
    p = Process(self, aCallable)
    self._processes.add(p)
    return p
  def DestroyProcess(self, p):
    q = [e for e in self_eventQueue if not e.process is p]
    if len(q) != len(self._eventQueue):
      heapq.heapify(q)
      self._eventQueue = q
    self._processes.remove(p)
  def PostInputTo(self, process, value):
    self.PostEvent(process, value, dt=0)
  def isInputAvailable(self, process):
    return process.eventCount > 0

  def PostEvent(self, process, value=None, dt=0, recurring=False, priority=DEFAULT_PRIORITY):
    "At time now+dt, send event to receiver. If recurring, repeat every dt."
    e = SimEvent(process, value, self._clock+dt, (None,dt)[recurring==True], priority)
    heapq.heappush(self._eventQueue, e)
    process.eventCount += 1

  def ExecEvent(self):
    "Execute the first event in the queue.  Advance the clock to match."
    e = heapq.heappop(self._eventQueue)
    e.process.eventCount -= 1
    self._clock = e.t_abs
    e.Exec()
    if e.recurrence:
      e.t_abs = self._clock + e.recurrence
      heapq.heappush(self._eventQueue, e)
      e.process.eventCount += 1

  def ExecEventsFor(self, dt=None, cycle_limit=None, process=None):
    '''Execute events from the queue:
        * up to but not including time (Now + dt)
          - if dt is 0, execute any events at time Now
        * up to and including cycle_limit number of events
        * while the given process still has pending events
      - advance the clock by dt if no earlier events are still pending
      - return the number of events executed
    '''
    #print self._clock, dt, len(self._eventQueue), self._eventQueue[0]
    assert dt          is None or dt          >= 0
    assert cycle_limit is None or cycle_limit >= 0
    assert process     is None or isinstance(process, Process)
    assert not (dt is None and cycle_limit is None and process is None) # you sure you want to run forever?
    if not dt is None:
      stop_time = self._clock+dt
    c = 0
    # Process events until time or cycles run out.
    while self._eventQueue and c != cycle_limit:
      if not dt is None:
        if dt==0:
          if self._eventQueue[0].t_abs > stop_time:
            break
        elif self._eventQueue[0].t_abs >= stop_time:
          break
      if not process is None and process.eventCount == 0:
        break
      self.ExecEvent()  # updates clock
      c += 1
    if not self._eventQueue or (not dt is None and self._eventQueue[0].t_abs >= stop_time):
      # No further events scheduled for before stop_time, so ensure clock progression.
      self._clock = stop_time
    return c

  def Now(self): return self._clock

  def HowLongUntilNext(self):
    if self._eventQueue:
      return self._eventQueue[0][0] - self._clock
    return None

if __name__=='__main__': unittest.main()
