
import Queue
from .ordered_set import OrderedSet


class OrderedSetQueue(Queue.Queue):
    def _init(self, maxsize):
        self.queue = OrderedSet()

    def _put(self, item):
        self.queue.add(item)

    def _get(self):
        return self.queue.pop()


class CheckableOrderedSetQueue(OrderedSetQueue):
    """ This is really not safe, as it allows for race conditions to exist say if the
        object disappears after it was checked for. """
    def __contains__(self, item):
        with self.mutex:
            return item in self.queue
