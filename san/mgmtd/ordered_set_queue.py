
import Queue
from .ordered_set import OrderedSet


class OrderedSetQueue(Queue.Queue):
    def _init(self, maxsize):
        self.queue = OrderedSet()

    def _put(self, item):
        self.queue.add(item)

    def _get(self):
        return self.queue.pop()
