/**
 * @file button.c
 * @brief Buton ISR (t0) ve ButtonTask (t1, t2) — orta öncelik.
 *
 * ISR kısa tutulur: damga, bayrak temizleme, filtre, kuyruğa kopya. Beklemez,
 * UART'a yazmaz.
 */
#include "app.h"
#include "main.h"
#include "app_config.h"
#include "event_log.h"
#include "msg.h"
#include "scenario.h"
#include "timebase.h"
#include <string.h>

#define BTN_PIN_MASK   (1u << 0)     /* PA0 = B1 (aktif yüksek)          */

static uint32_t s_last_edge_us;
static bool     s_have_edge;
static uint32_t s_idle_press_us;   /* boştaki (ölçüm dışı) basışın başlangıcı */
static bool     s_idle_down;

typedef enum { EDGE_NONE, EDGE_MEASURE, EDGE_IDLE_PRESS, EDGE_IDLE_RELEASE } edge_t;

/*
 * Basış kenarı + 30 ms tekrar-kenar filtresi.
 * EXTI iki kenarda da tetiklenir; böylece bırakma sıçramaları da görülüp atılır.
 *  - Önceki HERHANGİ bir kenardan 30 ms geçmeden gelen kenar: sıçrama, sayılır, atılır.
 *  - Ölçüm açıkken sessizlikten sonra gelen yükselen kenar: ölçülen basış (gecikmesiz).
 *  - Ölçüm kapalıyken: basış/bırakma süresine göre kontrol (kısa: sonraki senaryo,
 *    uzun: START). Ölçüm yolundaki davranış değişmez.
 */
static edge_t classify_edge(uint32_t now)
{
    const bool level_high = (GPIOA->IDR & BTN_PIN_MASK) != 0u;
    const bool quiet = !s_have_edge || elapsed_us(s_last_edge_us, now) >= DEBOUNCE_US;

    s_last_edge_us = now;
    s_have_edge = true;

    if (!quiet) {
        g_cnt.bounce++;
        return EDGE_NONE;
    }
    if (g_started) {
        if (!level_high) {
            return EDGE_NONE;                     /* bırakma kenarı */
        }
        if (g_stop_pending || (int32_t)(now - g_arm_at_us) < 0) {
            g_cnt.ignored++;                      /* 5 s ısınma / otomatik durdurma */
            return EDGE_NONE;
        }
        return EDGE_MEASURE;
    }
    if (level_high) {
        s_idle_down = true;
        s_idle_press_us = now;
        return EDGE_IDLE_PRESS;
    }
    if (s_idle_down) {
        s_idle_down = false;
        return EDGE_IDLE_RELEASE;
    }
    return EDGE_NONE;
}

static void post_cmd_isr(const char *text, BaseType_t *wake)
{
    cmd_t c;
    strncpy(c.text, text, sizeof c.text - 1u);
    c.text[sizeof c.text - 1u] = '\0';
    (void)xQueueSendFromISR(g_cmd_q, &c, wake);
}

void EXTI0_IRQHandler(void)
{
    const uint32_t now = timer_us();          /* t0: ISR girişi */
    EXTI->PR = BTN_PIN_MASK;                  /* bayrağı temizle (1 yazarak) */

    const edge_t edge = classify_edge(now);
    BaseType_t wake = pdFALSE;

    if (edge == EDGE_MEASURE) {
        g_cnt.accepted++;
        button_event_t e = { .id = evlog_open_isr(now), .t0_us = now };
        if (xQueueSendFromISR(g_button_q, &e, &wake) != pdPASS) {
            g_cnt.btn_q_drop++;
            evlog_status(e.id, EV_BTN_DROP);
        }
        if (g_cnt.accepted >= AUTO_STOP_EVENTS) {
            g_stop_pending = true;            /* yeni basış kabul edilmez; UartTxTask bitirir */
        }
    } else if (edge == EDGE_IDLE_RELEASE) {
        const bool long_press = elapsed_us(s_idle_press_us, now) >= CTL_LONG_PRESS_US;
        post_cmd_isr(long_press ? "START" : "SCNNEXT", &wake);
    }
    portYIELD_FROM_ISR(wake);
}

void button_init_irq(void)
{
    /* PA0 GPIO/EXTI ayarı main.c'de (MX_GPIO_Init). Öncelik 5 =
       configMAX_SYSCALL_INTERRUPT_PRIORITY: FreeRTOS FromISR API çağrılabilir. */
    EXTI->PR = BTN_PIN_MASK;
    HAL_NVIC_SetPriority(EXTI0_IRQn, 5, 0);
    HAL_NVIC_EnableIRQ(EXTI0_IRQn);
}

static bool make_button_reply(tx_msg_t *m, uint32_t id)
{
    sb_t sb;
    m->kind = MSG_BTN;
    m->event_id = id;
    sb_init(&sb, m->data, sizeof m->data);
    sb_str(&sb, "BTN,");
    sb_u32(&sb, id);
    sb_char(&sb, ',');
    sb_str(&sb, scenario_current()->name);
    sb_str(&sb, ",PRESSED");
    return msg_seal_fixed(&sb);
}

void button_task(void *arg)
{
    (void)arg;
    button_event_t e;
    tx_msg_t m;

    for (;;) {
        (void)xQueueReceive(g_button_q, &e, portMAX_DELAY);
        evlog_set(e.id, T1, timer_us());               /* t1: olay alındı */

        HAL_GPIO_TogglePin(LED_PORT, LED_BLUE_PIN);   /* görsel yanıt */

        if (!make_button_reply(&m, e.id)) {
            g_cnt.fmt_error++;
            evlog_status(e.id, EV_TX_ERROR);
            continue;
        }

        evlog_set(e.id, T2, timer_us());               /* t2: xQueueSend'den hemen önce */
        if (xQueueSend(g_tx_q, &m, 0) != pdPASS) {
            g_cnt.btn_tx_drop++;
            evlog_status(e.id, EV_TX_DROP);
        }
    }
}
