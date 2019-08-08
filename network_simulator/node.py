import copy
import random

from bloom_clock.bloom_clock import BloomClock
from network_simulator.clock import LamportClock
from crdt.gset import GSet
import operator

from network_simulator.conflict import Conflict
from network_simulator.message import Message

from bloom_clock.bloom_clock_operations import *


class Node(object):

    def __init__(self, id, length):

        self.id = id
        self.messages = [[] for i in range(length * 50)]
        self.bloom_messages = [[] for i in range(length * 50)]
        self.up = random.randint(1, 10)
        self.down = random.randint(1, self.up)
        self.is_dropped = False
        self.reactivation_time = -1
        self.incrementer = None
        self.message_queue = []
        self.pending_messages = []
        self.stats = None
        self.bloom_stats = None

        self.clock = LamportClock()
        self.length = length
        self.operations = GSet()

        # env.process(self.run())

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, self.id)

    def change_type(self,type):
        if type == "bloom":
            self.clock = BloomClock(self.length)

    def receive_clock_broadcast(self, time):
        self.get_message(time)

    def get_message(self, time):
        if self.is_dropped:
            if len(self.messages[time]) > 0:
                ops = []
                for m in self.messages[time]:
                    # print("*********** " + str(m) + " ****************")
                    ops.append(m)
                ops = sorted(ops)
                for o in ops:
                    self.add_to_message_queue(o)

        elif len(self.messages[time]) > 1:
            print("conflict resolution time")
            self.conflict_resolution(time)
        elif len(self.messages[time]) == 1:
            m = self.messages[time][0]
            self.handle_message(m, time)
        else:
            # print "never getting in here"
            pass

    def disconnect(self, disruption):
        self.is_dropped = True
        self.reactivation_time = disruption.end_time

    def reactivate(self,timestamp):
        self.is_dropped = False
        self.handle_message_backlog(timestamp)

    def send(self,msg):
        self.clock.send_event(id(msg))
        msg.set_clock(self.clock.get_clock())
        msg.clock = self.clock.get_clock()
        if self.is_dropped:
            # print("putting this message into the pending queue: " + str(msg))
            self.pending_messages.append(msg)
        else:
            msg.receiver.receive(msg)
            self.add_to_opset(msg)

    def receive(self, msg):
        # print "RECEIVING TO BE CONSUMED AT:  " + str(msg.time_sent) + " + " + str(delay)
        self.add_to_messages(msg, msg.receive_time)

    def add_to_messages(self, msg, index):
        # print index
        # print self.id + " adding message from " + msg.sender.id
        self.messages[index].append(msg)

    def add_to_message_queue(self, msg):
        self.message_queue.append(msg)

    def handle_message(self, msg, time):
        self.add_to_opset(msg)
        i = self.messages[time].index(msg)
        self.messages[time][i] = None
        self.incrementer()
        self.clock = self.clock.receive_event(msg.clock)
        print(self.id + " receiving message from " + msg.sender.id)

    def handle_message_backlog(self,timestamp):
        # print(list(self.message_queue.queue))
        while len(self.message_queue) > 0:
            msg = self.message_queue.pop(0)
            self.clock = self.clock.receive_event(msg.clock)
            self.incrementer()


        while len(self.pending_messages):
            # print("======>")
            # print(m)
            m = self.pending_messages.pop(0)
            m.readjust(timestamp)
            # print("readjusting ===>")
            # print(m)
            m.receiver.receive(m)

    def conflict_resolution(self,time):
        print("resolving conflicts....")
        ops = []
        for m in self.messages[time]:
            ops.append(m)

        ops = sorted(ops)

        if isinstance(self.clock,LamportClock):
            confl = Conflict(ops)
        if isinstance(self.clock,BloomClock):
            confl = Conflict(ops,"bloom")

        # self.stats.record_conflict(confl)
        self.stats.record_conflict(confl)

        for o in ops:
            self.add_to_opset(o)
            self.handle_message(o,time)

    def add_to_opset(self,op):
        self.operations.add(op)

