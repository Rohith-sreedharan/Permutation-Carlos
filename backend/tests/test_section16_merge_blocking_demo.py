"""
Section 16: CI/CD Merge-Blocking Demonstration

This test is intentionally designed to FAIL initially to demonstrate
branch protection enforcement. Once screenshots are captured, it will
be fixed to demonstrate merge unblocking.

DO NOT DELETE - Required for Section 16 evidence pack.
"""


def test_merge_blocking_enforcement_INTENTIONAL_FAIL():
    """
    INTENTIONAL FAILURE - Demonstrates CI/CD merge blocking.
    
    This test MUST fail to show that branch protection prevents
    merging when CI checks fail. After capturing screenshots of
    the blocked state, this will be fixed to show unblocking.
    """
    assert False, "INTENTIONAL FAILURE: Demonstrating Section 16 merge-blocking enforcement"


def test_merge_blocking_basic_sanity():
    """Sanity check that other tests still pass."""
    assert True, "Basic sanity check passes"
