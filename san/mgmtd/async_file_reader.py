
import time
import subprocess
import threading
import Queue


class AsynchronousFileReader(threading.Thread):
    '''
    Helper class to implement asynchronous reading of a file
    in a separate thread. Pushes read lines on a queue to
    be consumed in another thread.
    '''

    def __init__(self, fd, queue):
        assert isinstance(queue, Queue.Queue)
        assert callable(fd.readline)
        threading.Thread.__init__(self)
        self._fd = fd
        self._queue = queue

    def run(self):
        '''The body of the tread: read lines and put them on the queue.'''
        for line in iter(self._fd.readline, ''):
            self._queue.put(line)

    def eof(self):
        '''Check whether there is no more content to expect.'''
        return not self.is_alive() and self._queue.empty()


class AsynchronousFileLogger(threading.Thread):
    '''
    Helper class to implement asynchronous reading of a file
    in a separate thread. Logs read lines.
    '''

    def __init__(self, fd, logger, log_prefix):
        assert callable(fd.readline)
        threading.Thread.__init__(self)
        self._fd = fd
        self._logger = logger
        self._log_prefix = log_prefix

    def run(self):
        '''The body of the tread: read lines and put them on the queue.'''
        for line in iter(self._fd.readline, ''):
            line = line.rstrip("\n")
            self._logger.info('%s: %s', self._log_prefix,
                              #repr(line),
                              line,
                              )

    def eof(self):
        '''Check whether there is no more content to expect.'''
        return not self.is_alive()


def consume(command):
    '''
    Example of how to consume standard output and standard error of
    a subprocess asynchronously without risk on deadlocking.
    '''

    # Launch the command as subprocess.
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Launch the asynchronous readers of the process' stdout and stderr.
    stdout_queue = Queue.Queue()
    stdout_reader = AsynchronousFileReader(process.stdout, stdout_queue)
    stdout_reader.start()
    stderr_queue = Queue.Queue()
    stderr_reader = AsynchronousFileReader(process.stderr, stderr_queue)
    stderr_reader.start()

    # Check the queues if we received some output (until there is nothing more to get).
    while not stdout_reader.eof() or not stderr_reader.eof():
        # Show what we received from standard output.
        while not stdout_queue.empty():
            line = stdout_queue.get()
            print 'Received line on standard output: ' + repr(line)

        # Show what we received from standard error.
        while not stderr_queue.empty():
            line = stderr_queue.get()
            print 'Received line on standard error: ' + repr(line)

        # Sleep a bit before asking the readers again.
        time.sleep(.1)

    # Let's be tidy and join the threads we've started.
    stdout_reader.join()
    stderr_reader.join()

    # Close subprocess' file descriptors.
    process.stdout.close()
    process.stderr.close()
