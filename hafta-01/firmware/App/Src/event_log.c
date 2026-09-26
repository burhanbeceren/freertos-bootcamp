/**
 * @file event_log.c
 */
#include "event_log.h"
#include "app_config.h"
#include "FreeRTOS.h"
#include "task.h"
#include <string.h>

ev_counters_t g_cnt;

static ev_rec_t          s_log[LOG_CAPACITY];
static volatile uint32_t s_next_id;   /* son verilen kimlik; yalnız ISR artırır */

static ev_rec_t *rec(uint32_t id)
{
    return (id >= 1u && id <= LOG_CAPACITY) ? &s_log[id - 1u] : NULL;
}

void evlog_reset(void)
{
    taskENTER_CRITICAL();
    memset(s_log, 0, sizeof s_log);
    memset((void *)&g_cnt, 0, sizeof g_cnt);
    s_next_id = 0;
    taskEXIT_CRITICAL();
}

uint32_t evlog_open_isr(uint32_t t0)
{
    const uint32_t id = ++s_next_id;
    ev_rec_t *r = rec(id);
    if (r != NULL) {
        r->t[T0]  = t0;
        r->have   = (uint8_t)(1u << T0);
        r->status = EV_PENDING;
    } else {
        g_cnt.log_overflow++;
    }
    return id;
}

void evlog_set(uint32_t id, int idx, uint32_t t)
{
    ev_rec_t *r = rec(id);
    if (r != NULL) {
        r->t[idx] = t;
        r->have  |= (uint8_t)(1u << idx);
    }
}

void evlog_status(uint32_t id, ev_status_t st)
{
    ev_rec_t *r = rec(id);
    if (r != NULL) {
        r->status = (uint8_t)st;
    }
}

void evlog_finalize(void)
{
    const uint32_t n = evlog_count();
    for (uint32_t i = 0; i < n; i++) {
        if (s_log[i].status == EV_PENDING) {
            s_log[i].status = EV_TIMEOUT;
        }
    }
}

uint32_t evlog_count(void)
{
    const uint32_t n = s_next_id;
    return (n > LOG_CAPACITY) ? LOG_CAPACITY : n;
}

bool evlog_get(uint32_t id, ev_rec_t *out)
{
    ev_rec_t *r = rec(id);
    if (r == NULL || id > s_next_id) {
        return false;
    }
    *out = *r;
    return true;
}

const char *evlog_status_str(uint8_t st)
{
    switch (st) {
    case EV_OK:       return "ok";
    case EV_BTN_DROP: return "btn_drop";
    case EV_TX_DROP:  return "tx_drop";
    case EV_TX_ERROR: return "tx_error";
    case EV_TIMEOUT:  return "timeout";
    default:          return "pending";
    }
}
