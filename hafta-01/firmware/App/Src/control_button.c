/**
 * @file control_button.c
 * @brief Deney kontrol butonu (PE7). ÖLÇÜLEN buton DEĞİLDİR.
 *
 * PC'den komut göndermeye gerek kalmadan deneyi karttan yönetir:
 *   Boştayken kısa basış (< 1 s)  -> sonraki senaryo    ("SCNNEXT")
 *   Boştayken uzun basış (>= 1 s) -> START + 5 s ısınma  ("START")
 *   Ölçüm sırasında basış         -> STOP + DUMP         ("STOPDUMP")
 *
 * ISR yalnızca komut kuyruğuna metin bırakır; komutu UART'ın tek sahibi olan
 * UartTxTask işler (PC'den gelen komutlarla aynı yol).
 *
 * Bağlantı: butonun bir ucu PE7, diğer ucu GND. Dahili pull-up açık (aktif düşük).
 */
#include "app.h"
#include "app_config.h"
#include "timebase.h"
#include <string.h>

#define CTL_PIN_MASK      (1u << 7)       /* PE7 */

static uint32_t s_last_edge_us;
static bool     s_have_edge;
static uint32_t s_press_us;
static bool     s_pressed;
static bool     s_consumed;     /* basış anında işlendi; bırakma yok sayılır */

static void post_cmd_isr(const char *text, BaseType_t *wake)
{
    cmd_t c;
    strncpy(c.text, text, sizeof c.text - 1u);
    c.text[sizeof c.text - 1u] = '\0';
    (void)xQueueSendFromISR(g_cmd_q, &c, wake);
}

void EXTI9_5_IRQHandler(void)
{
    const uint32_t now = timer_us();
    if ((EXTI->PR & CTL_PIN_MASK) == 0u) {
        return;
    }
    EXTI->PR = CTL_PIN_MASK;

    /* 30 ms sessizlik filtresi (ölçülen butonla aynı kural) */
    const bool quiet = !s_have_edge || elapsed_us(s_last_edge_us, now) >= DEBOUNCE_US;
    s_last_edge_us = now;
    s_have_edge = true;
    if (!quiet) {
        return;
    }

    const bool down = (GPIOE->IDR & CTL_PIN_MASK) == 0u;   /* aktif düşük */
    BaseType_t wake = pdFALSE;

    if (down && !s_pressed) {
        s_pressed = true;
        s_press_us = now;
        s_consumed = false;
        if (g_started) {
            post_cmd_isr("STOPDUMP", &wake);
            s_consumed = true;
        }
    } else if (!down && s_pressed) {
        s_pressed = false;
        if (!s_consumed && !g_started) {
            const bool long_press = elapsed_us(s_press_us, now) >= CTL_LONG_PRESS_US;
            post_cmd_isr(long_press ? "START" : "SCNNEXT", &wake);
        }
    }
    portYIELD_FROM_ISR(wake);
}

void control_button_init_irq(void)
{
    /* PE7 GPIO/EXTI ayarı main.c'de. Ölçülen butondan (5) daha düşük öncelik. */
    EXTI->PR = CTL_PIN_MASK;
    HAL_NVIC_SetPriority(EXTI9_5_IRQn, 7, 0);
    HAL_NVIC_EnableIRQ(EXTI9_5_IRQn);
}
