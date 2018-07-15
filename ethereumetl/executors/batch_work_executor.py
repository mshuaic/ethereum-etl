# MIT License
#
# Copyright (c) 2018 Evgeny Medvedev, evge.medvedev@gmail.com
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


from web3.utils.threads import Timeout

from ethereumetl.executors.bounded_executor import BoundedExecutor
from ethereumetl.executors.fail_safe_executor import FailSafeExecutor
from ethereumetl.utils import dynamic_batch_iterator


# Executes the given work in batches, reducing the batch size exponentially in case of errors.
class BatchWorkExecutor:
    def __init__(self, starting_batch_size, max_workers, retry_exceptions=(Timeout, OSError)):
        self.batch_size = starting_batch_size
        self.max_workers = max_workers
        self.executor = FailSafeExecutor(BoundedExecutor(1, self.max_workers))
        self.retry_exceptions = retry_exceptions

    def execute(self, work_iterable, work_handler):
        for batch in dynamic_batch_iterator(work_iterable, lambda: self.batch_size):
            self.executor.submit(self._fail_safe_execute, work_handler, batch)

    # Check race conditions
    def _fail_safe_execute(self, work_handler, batch):
        try:
            work_handler(batch)
        except Exception as ex:
            if type(ex) in self.retry_exceptions:
                batch_size = self.batch_size
                # If can't reduce the batch size further then raise
                if batch_size == 1:
                    raise ex
                # Reduce the batch size. Subsequent batches will be 2 times smaller
                if batch_size == len(batch):
                    self.batch_size = max(1, int(batch_size / 2))
                # For the failed batch try handling items one by one
                for item in batch:
                    work_handler([item])
            else:
                raise ex

    def shutdown(self):
        self.executor.shutdown()
