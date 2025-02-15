"""
Timing utilities for Instagram automation.
Provides functions for managing delays between actions to simulate human behavior.
"""

import asyncio
import random
from typing import Optional
from ..config import MIN_ACTION_DELAY, MAX_ACTION_DELAY, MIN_BATCH_DELAY, MAX_BATCH_DELAY

async def wait_random_interval(
    min_seconds: Optional[float] = None,
    max_seconds: Optional[float] = None
) -> None:
    """
    Wait for a random interval between min_seconds and max_seconds.
    
    Args:
        min_seconds: Minimum wait time in seconds
        max_seconds: Maximum wait time in seconds
    """
    min_secs = min_seconds if min_seconds is not None else MIN_ACTION_DELAY
    max_secs = max_seconds if max_seconds is not None else MAX_ACTION_DELAY
    delay = random.uniform(min_secs, max_secs)
    await asyncio.sleep(delay)

async def wait_between_actions() -> None:
    """Wait for a short random interval between individual actions."""
    await wait_random_interval(MIN_ACTION_DELAY, MAX_ACTION_DELAY)

async def wait_between_batches() -> None:
    """Wait for a longer random interval between batches of actions."""
    await wait_random_interval(MIN_BATCH_DELAY, MAX_BATCH_DELAY)

def calculate_batch_schedule(total_actions: int, batches: int) -> list[int]:
    """
    Calculate a slightly randomized distribution of actions across batches.
    
    Args:
        total_actions: Total number of actions to distribute
        batches: Number of batches to distribute actions across
    
    Returns:
        List of action counts for each batch
    """
    base_per_batch = total_actions // batches
    remainder = total_actions % batches
    
    # Start with base distribution
    distribution = [base_per_batch for _ in range(batches)]
    
    # Add remainder randomly
    for _ in range(remainder):
        idx = random.randint(0, batches - 1)
        distribution[idx] += 1
    
    # Add small random variations while maintaining total
    for i in range(batches):
        if distribution[i] > 2:  # Only vary if we have room
            variation = random.randint(-1, 1)
            if 0 <= i + 1 < batches:  # If we can balance with next batch
                distribution[i] += variation
                distribution[i + 1] -= variation
    
    return distribution 