/**
 * @file telemetry.c
 * @brief TelemetryTask — yüksek öncelik. Periyodik veri üretir, TX kuyruğuna bırakır.
 *
 * S0'da (telemetri kapalı) görev bildirim bekleyerek bloklu kalır.
 */
#include "app.h"
#include "app_config.h"
#include "event_log.h"
#include "msg.h"
#include "scenario.h"
#include "timebase.h"
#include "work.h"

static volatile bool     s_run;
static volatile uint32_t s_gen;   /* her START'ta artar: eski döngü parametreleri bırakılır */

/* Doğrulama istatistikleri: gerçek periyot ve gerçek CPU işi süresi */
static volatile uint32_t s_per_min, s_per_max, s_work_min, s_work_max;

void telemetry_start(void)
{
    s_per_min = UINT32_MAX; s_per_max = 0;
    s_work_min = UINT32_MAX; s_work_max = 0;
    s_gen++;
    s_run = (scenario_current()->period_ms != 0u);
    if (s_run) {
        xTaskNotifyGive(g_tel_task);
    }
}

void telemetry_stop(void)
{
    s_run = false;   /* Görev bir sonraki uyanışta bloklanır */
}

void telemetry_stats(uint32_t *per_min, uint32_t *per_max,
                     uint32_t *work_min, uint32_t *work_max)
{
    *per_min  = (s_per_min  == UINT32_MAX) ? 0u : s_per_min;
    *per_max  = s_per_max;
    *work_min = (s_work_min == UINT32_MAX) ? 0u : s_work_min;
    *work_max = s_work_max;
}

static bool make_telemetry(tx_msg_t *m, uint32_t seq, uint32_t work_us, uint32_t chk)
{
    sb_t sb;
    m->kind = MSG_TEL;
    m->event_id = seq;
    sb_init(&sb, m->data, sizeof m->data);
    sb_str(&sb, "TEL,");
    sb_u32(&sb, seq);
    sb_char(&sb, ',');
    sb_str(&sb, scenario_current()->name);
    sb_char(&sb, ',');
    sb_u32(&sb, timer_us());      /* MCU saatinde üretim anı (faz analizi için) */
    sb_char(&sb, ',');
    sb_u32(&sb, work_us);
    sb_char(&sb, ',');
    sb_u32(&sb, chk & 0xFFFFu);
    return msg_seal_fixed(&sb);
}

void telemetry_task(void *arg)
{
    (void)arg;
    tx_msg_t m;
    uint32_t seq = 0;

    for (;;) {
        /* Kapalıyken bloklu bekle (CPU tüketme) */
        while (!s_run) {
            (void)ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        }

        const uint32_t gen = s_gen;
        const scenario_t *sc = scenario_current();
        const TickType_t period = pdMS_TO_TICKS(sc->period_ms);
        const uint32_t iters = work_iters_for_us(sc->work_us);
        TickType_t last = xTaskGetTickCount();
        uint32_t prev_start = 0;
        bool first = true;
        seq = 0;

        while (s_run && gen == s_gen) {
            const uint32_t start = timer_us();
            if (!first) {
                const uint32_t p = elapsed_us(prev_start, start);
                if (p < s_per_min) s_per_min = p;
                if (p > s_per_max) s_per_max = p;
            }
            prev_start = start;
            first = false;

            const uint32_t chk = (iters != 0u) ? work_run(iters) : 0u;   /* calibrated_work */
            const uint32_t w = elapsed_us(start, timer_us());
            if (iters != 0u) {
                if (w < s_work_min) s_work_min = w;
                if (w > s_work_max) s_work_max = w;
            }

            if (make_telemetry(&m, ++seq, w, chk)) {
                if (xQueueSend(g_tx_q, &m, 0) != pdPASS) {
                    g_cnt.tel_tx_drop++;
                } else {
                    g_cnt.tel_sent++;
                }
            } else {
                g_cnt.fmt_error++;
            }

            vTaskDelayUntil(&last, period);
        }
    }
}
