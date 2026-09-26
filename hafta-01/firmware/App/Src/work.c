/**
 * @file work.c
 */
#include "work.h"
#include "timebase.h"

#define CAL_ITERS 200000u

static uint32_t s_iters_per_ms = 1u;
static volatile uint32_t s_sink;

uint32_t work_run(uint32_t iters)
{
    uint32_t x = 2463534242u;
    for (uint32_t i = 0; i < iters; i++) {
        x ^= x << 13;
        x ^= x >> 17;
        x ^= x << 5;
        __asm__ volatile("" : "+r"(x));   /* döngünün katlanmasını/vektörleşmesini engeller */
    }
    return x;
}

void work_calibrate(void)
{
    (void)work_run(1000u);                 /* ART cache ısınması */

    const uint32_t a = timer_us();
    s_sink = work_run(CAL_ITERS);
    const uint32_t us = elapsed_us(a, timer_us());

    s_iters_per_ms = (uint32_t)(((uint64_t)CAL_ITERS * 1000u) / (us ? us : 1u));
}

uint32_t work_iters_per_ms(void)
{
    return s_iters_per_ms;
}

uint32_t work_iters_for_us(uint32_t us)
{
    return (uint32_t)(((uint64_t)s_iters_per_ms * us) / 1000u);
}
