import asyncio
import time
import threading

from agile.utils.timing import timing_stack


@timing_stack(
    func_name="demo_async_top",
    include="all",
    output_format="text",
    warning_at=1000,
    include_patterns="__main__.**",
    # exclude_patterns=["asyncio.**", "threading.**", "selectors.**", "_weakrefset.**", "agile.utils.timing.**"],
    include_protected=False,
    include_private=True,
    include_magic=False,
)
async def demo_async_top():
    """Async top-level function that calls sync and async subcalls."""
    sync_a()
    await async_a()
    await async_b()
    # spawn a thread and wait for it to finish (top-level wall-clock should include it)
    t = threading.Thread(target=threaded_work, name="worker-thread")
    t.start()
    t.join()


def sync_a():
    # sync function that calls another sync function
    sync_b()


def sync_b():
    time.sleep(0.5)  # simulate blocking IO / CPU-bound work


# @timing_stack(func_name="inner_async_a", include="all", output_format="text")
async def async_a():
    # async function that calls a small sync helper
    await asyncio.sleep(0.2)
    small_sync()


def small_sync():
    time.sleep(0.1)


async def async_b():
    # nested async calls
    await asyncio.sleep(0.3)
    await async_c()


async def async_c():
    await asyncio.sleep(0.15)


def threaded_work():
    # simulates work done in a background thread
    time.sleep(1.0)


@timing_stack(func_name="demo_filtered_top", include="all", output_format="text", include_patterns="__main__.**")
async def demo_filtered_top():
    """Filtered demo: only include functions from __main__ module in report."""
    sync_a()
    await async_a()
    await async_b()


@timing_stack(func_name="demo_sync_top", include="all", output_format="json")
def demo_sync_top():
    # Synchronous top-level example that calls nested sync functions and an async function (run via asyncio.run)
    sync_x()
    sync_y()
    # run a small async action from sync context
    asyncio.run(async_small())


def sync_x():
    time.sleep(0.2)
    sync_x_child()


def sync_x_child():
    time.sleep(0.05)


def sync_y():
    time.sleep(0.3)


async def async_small():
    await asyncio.sleep(0.25)


if __name__ == '__main__':
    # print("Running async demo (will take ~2s)...")
    start_time = time.time()
    asyncio.run(demo_async_top())
    print(f"Manual timing: {time.time() - start_time:.2f} seconds")


    # print("\nRunning sync demo (will take ~1s)...")
    # start_time = time.time()
    # demo_sync_top()
    # print(f"Manual timing: {time.time() - start_time:.2f} seconds")

    # print("\nRunning filtered demo (include only __main__.*) (will take ~1s)...")
    # # 计时开始
    # start_time = time.time()
    # asyncio.run(demo_filtered_top())
    # print(f"Manual timing: {time.time() - start_time:.2f} seconds")

