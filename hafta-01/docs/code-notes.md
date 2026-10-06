# Kod Notları: ISR, Görevler, UART Tamamlanması, Zaman Hesapları

Bu dosya kritik kod bloklarını açıklar. Tam kaynak `firmware/App/Src/` altındadır.

## 1. Mimari

```
 B1 (PA0) ─EXTI0 ISR──(buttonQ, 8)──► ButtonTask (2) ──┐
            t0                          t1, t2          │  txQ (16, FIFO, 64 B)
                                                        ├──────────────► UartTxTask (1) ──DMA──► USART2 ──► PC
 TelemetryTask (3) ── iş + TEL ─────────────────────────┘                 t3 │  ▲ TC ISR → t4
                                                                              │  │
 PC komutları ─USART2 RX ISR──(cmdQ, 4)──────────────────────────────────────┘ (queue set)
```

3 uygulama görevi vardır. Idle bu sayıya dahil değildir; ISR bir görev değildir. `configUSE_TIMERS = 0` olduğu için timer servis görevi de yoktur.

| Görev | Öncelik | Sorumluluk |
|---|---|---|
| TelemetryTask | 3 (yüksek) | Periyodik veri üretir, ortak TX kuyruğuna bırakır. S4/S5'te ek CPU işi yapar. |
| ButtonTask | 2 (orta) | Buton olayını alır, "butona basıldı" yanıtını üretir, TX kuyruğuna bırakır. |
| UartTxTask | 1 (düşük) | FIFO kuyruğunu tüketir, UART gönderimini yönetir. **UART'ın tek sahibidir.** |

## 2. Buton ISR: kısa, kopyalanan olay, kontrol edilen sonuç

```c
void EXTI0_IRQHandler(void)
{
    const uint32_t now = timer_us();          /* t0: ISR girişi */
    EXTI->PR = BTN_PIN_MASK;                  /* bayrağı temizle */

    if (!accept_edge(now)) {
        return;
    }

    g_cnt.accepted++;
    button_event_t e = { .id = evlog_open_isr(now), .t0_us = now };

    BaseType_t wake = pdFALSE;
    if (xQueueSendFromISR(g_button_q, &e, &wake) != pdPASS) {
        g_cnt.btn_q_drop++;
        evlog_status(e.id, EV_BTN_DROP);
    }
    portYIELD_FROM_ISR(wake);
}
```

- **t₀ gerçekten girişte alınır.** Derlenmiş kodda `TIM2->CNT` okuması ISR'ın 4. komutudur (`ldr r4,[r0,#36]`). Bunu `arm-none-eabi-objdump -d build/hafta01.elf` çıktısında görebilirsiniz.
- **Tek global timestamp yoktur.** Olay kimliği ve t₀ birlikte kuyruğa **kopyalanır**; bir sonraki basış öncekinin zamanını ezemez.
- **Filtre (`accept_edge`):** EXTI iki kenarda tetiklenir. Önceki herhangi bir kenardan 30 ms geçmeden gelen kenar sıçrama sayılır (`bounce_rejected`) ve atılır. Sessizlikten sonra gelen yükselen kenar basıştır ve **gecikmeden** kabul edilir. Düşen kenar bırakmadır ve olay oluşturmaz. Böylece bırakma sıçramaları sahte basış üretmez.
- **5 s ısınma** ve ölçüm dışı basışlar `ignored` olarak sayılır, kimlik almaz.
- ISR içinde bekleme ve UART yazdırma yoktur. ISR önceliği 5'tir (= `configMAX_SYSCALL_INTERRUPT_PRIORITY`); bu yüzden FromISR API çağrılabilir.

## 3. ButtonTask: olay tabanlı yanıt

```c
for (;;) {
    (void)xQueueReceive(g_button_q, &e, portMAX_DELAY);
    evlog_set(e.id, T1, timer_us());               /* t1: olay alındı */
    HAL_GPIO_TogglePin(LED_PORT, LED_BLUE_PIN);    /* görsel yanıt */

    if (!make_button_reply(&m, e.id)) {            /* "BTN,<id>,<scn>,PRESSED" → 64 B */
        g_cnt.fmt_error++;
        evlog_status(e.id, EV_TX_ERROR);
        continue;
    }
    evlog_set(e.id, T2, timer_us());               /* t2: xQueueSend'den hemen önce */
    if (xQueueSend(g_tx_q, &m, 0) != pdPASS) {     /* beklemez: dolu kuyruk = tx_drop */
        g_cnt.btn_tx_drop++;
        evlog_status(e.id, EV_TX_DROP);
    }
}
```

TX mesajı veriyi **ve** olay kimliğini taşır (`tx_msg_t.event_id`). Kuyruk mesajı kopyalar; bu yüzden yerel `m` tamponunun ömrüne güvenilmez. Metin `snprintf` yerine heap kullanmayan küçük bir oluşturucuyla (`msg.c`) yazılır; böylece t₂−t₁ kısa ve deterministik kalır.

## 4. TelemetryTask: periyodik üretim

```c
while (s_run && gen == s_gen) {
    const uint32_t start = timer_us();
    /* gerçek periyot min/maks: CNT,tel_period_*_us */
    const uint32_t chk = (iters != 0u) ? work_run(iters) : 0u;   /* calibrated_work */
    const uint32_t w = elapsed_us(start, timer_us());            /* CNT,work_*_us    */
    if (make_telemetry(&m, ++seq, w, chk)) {
        if (xQueueSend(g_tx_q, &m, 0) != pdPASS) g_cnt.tel_tx_drop++;
        else                                     g_cnt.tel_sent++;
    }
    vTaskDelayUntil(&last, period);
}
```

- S0'da `s_run = false` olur ve görev `ulTaskNotifyTake(portMAX_DELAY)` ile **bloklu** kalır; CPU tüketmez.
- `work_run` bir xorshift32 döngüsüdür. Sonuç TEL mesajına yazılır ve `__asm__ volatile("" : "+r"(x))` ile optimizasyonla silinmesi engellenir. Açılışta 200 000 iterasyon TIM2 ile ölçülür ve `iters_per_ms` hesaplanır (**kartınızda kalibrasyon**).
- `vTaskDelayUntil` ile periyot kaymaz. Tick dönüşümü `pdMS_TO_TICKS` ile yapılır: 1 kHz'de 10/20/100 ms = 10/20/100 tick. Gerçek periyot ölçülüp raporlanır.

## 5. UartTxTask ve UART tamamlanması: "DMA bitti" ≠ "son bit çıktı"

```c
static tx_result_t uart_send_wait(const char *buf, uint16_t len, uint32_t *t3, uint32_t *t4)
{
    (void)ulTaskNotifyTake(pdTRUE, 0);                  /* eski bildirimi temizle */
    *t3 = timer_us();                                   /* t3: başlatmadan hemen önce */
    if (HAL_UART_Transmit_DMA(&huart2, (uint8_t *)buf, len) != HAL_OK) {
        g_cnt.tx_error++;
        return TX_START_FAIL;                           /* olay: tx_error */
    }
    if (ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(TX_TIMEOUT_MS)) == 0u) {
        (void)HAL_UART_AbortTransmit(&huart2);          /* sonsuz bekleme yok */
        g_cnt.tx_timeout++;
        return TX_TIMEOUT;                              /* olay: timeout */
    }
    *t4 = s_tc_us;
    return TX_OK;
}

void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART2) {
        s_tc_us = timer_us();                           /* t4 */
        BaseType_t wake = pdFALSE;
        vTaskNotifyGiveFromISR(g_uarttx_task, &wake);
        portYIELD_FROM_ISR(wake);
    }
}
```

**Neden bu callback TC anıdır?** STM32F4 HAL'de DMA aktarımı bittiğinde `UART_DMATransmitCplt`, DMA isteğini kapatır ve **TCIE**'yi açar. `HAL_UART_TxCpltCallback`, USART **TC** bayrağı kalktığında çağrılır: son baytın stop biti hattan çıktığında (`UART_EndTransmit_IT`). "DMA bitti" anında ise son iki bayt hâlâ gönderici tamponu ve kaydırma yazmacındadır.

- Gönderilen tampon (`s_cur`) statiktir ve TC gelene kadar yeniden kullanılmaz: tampon aktarım sonuna kadar yaşar.
- t₃ ve t₄ kaydı `m->event_id` ile kapatılır: kayıt doğru olay kimliğiyle kapanır.
- t₄ yanıt gönderildikten sonra bilinir; aynı yanıtın içine konamaz. Bu yüzden zaman damgaları deney sonunda `DUMP` ile ayrıca aktarılır.

**RX ve HAL kilidi:** RX için `HAL_UART_Receive_IT` kullanılmaz; HAL'in UART kilidi TX yoluyla yarışabilir. `USART2_IRQHandler` önce `SR`'yi, sonra `DR`'yi okuyup baytı alır; ardından TC işleme için `HAL_UART_IRQHandler` çağrılır.

**Queue set:** UartTxTask hem `txQ` hem `cmdQ` üzerinde `xQueueSelectFromSet` ile bekler; boşta periyodik uyanma yoktur. STOP sırasında `txQ` doğrudan boşaltılır. Sette kalan bayat tutamaçlar `xQueueReceive(..., 0)` başarısız olunca atlanır; bu yüzden set kapasitesi 2 × 16 + 4 tutulmuştur.

## 6. Kayıt ve zaman hesapları

```c
typedef struct { uint32_t t[5]; uint8_t have; uint8_t status; } ev_rec_t;   /* 128 olay */
```

- Her alanı tek bir bağlam yazar: t₀ ISR, t₁/t₂ ButtonTask, t₃/t₄/durum UartTxTask. Okuma yalnızca STOP'tan sonra (DUMP) yapılır. Bu yüzden kilit gerekmez.
- `have` bit maskesi eksik zamanı gösterir; eksik zaman CSV'ye **boş** yazılır, 0 yazılmaz.
- 128'den fazla olayda kayıt tutulmaz ve `log_overflow` artar.
- Farklar `uint32_t` çıkarmayla, yani mod 2³² hesaplanır (`elapsed_us`, Python'da `diff_us`). TIM2 71,6 dakikada bir sarar; bir olay (< 1 s) bir sayaç turundan çok kısadır.

| Hesap | Anlamı |
|---|---|
| t₁ − t₀ | ISR'den görevin olayı almasına kadar gözlenen süre |
| t₂ − t₁ | Yanıt hazırlama aralığı; preemption dahil olabilir |
| t₃ − t₂ | Kuyruğa verme + bekleme + UART başlatma öncesi süre |
| t₄ − t₃ | UART başlatma, hat aktarımı ve TC gözlem süresi |
| R = t₄ − t₀ | Kart tarafında toplam gözlenen yanıt süresi |

## 7. Deney kontrolü karttan (mavi buton + otomatik durdurma)

Ölçülen buton aynı zamanda deneyi yönetir. Ölçüm yolu değişmez: `EXTI0_IRQHandler` ilk komutta t₀'ı okur. Kenar sınıflandırması ölçüm açıkken önceki davranışla aynıdır.

```c
if (g_started) {                         /* ölçüm: yükselen kenar = olay */
    if (!level_high) return EDGE_NONE;
    if (g_stop_pending || (int32_t)(now - g_arm_at_us) < 0) { g_cnt.ignored++; return EDGE_NONE; }
    return EDGE_MEASURE;
}
/* boşta: basış süresine göre kontrol */
if (level_high) { s_idle_down = true; s_idle_press_us = now; return EDGE_IDLE_PRESS; }
if (s_idle_down) { s_idle_down = false; return EDGE_IDLE_RELEASE; }   /* kısa: SCNNEXT, uzun: START */
```

**Otomatik durdurma** yanlılık yaratmayacak şekilde çalışır. 30. olay kabul edilince ISR `g_stop_pending = true` yapar ve yeni basış kabul edilmez. Telemetri ve CPU yükü **açık kalır**. UartTxTask her mesajdan sonra (ve 50 ms'de bir) `evlog_all_closed()` ile bütün olayların kapandığını kontrol eder. 30. olayın yanıtı hattan çıkınca ya da kayıp olarak işaretlenince STOP + DUMP yapar. Böylece son olay da diğerleriyle aynı koşulda ölçülür.

## 8. Gecikme azaltma varyantları (A/B/C)

```c
/* ButtonTask: A ortak TX FIFO'ya, B/C öncelikli yanıt kuyruğuna yazar */
QueueHandle_t q = (g_variant == VAR_A) ? g_tx_q : g_reply_q;
evlog_set(e.id, T2, timer_us());               /* t2 */
if (xQueueSend(q, &m, 0) != pdPASS) { ... tx_drop ... }

/* UartTxTask: her uyanışta tam bir öğe, öncelik yanıt > komut > TEL */
if (xQueueReceive(g_reply_q, &s_cur, 0) == pdPASS)      send_queued(&s_cur);
else if (xQueueReceive(g_cmd_q, &c, 0) == pdPASS)       handle_cmd(&c);
else if (xQueueReceive(g_tx_q, &s_cur, 0) == pdPASS)    send_queued(&s_cur);

/* C: öncelikler çalışma anında değiştirilir (yalnız ölçüm dışında) */
vTaskPrioritySet(g_btn_task, 4); vTaskPrioritySet(g_uarttx_task, 3); vTaskPrioritySet(g_tel_task, 2);
```

- **B**, A'daki "yanıt kuyruktaki TEL'lerin arkasında bekler" sorununu hedefler. O anda hatta olan mesaj kesilemez; bu yüzden bekleme en fazla bir mesaj süresi (~5,55 ms) olur.
- **C**, iki şeyi daha giderir: ButtonTask CPU işinin bitmesini beklemez (t₁−t₀ ≈ 7 µs kalır). UartTxTask CPU işinden önce çalışır; TC gelir gelmez sıradaki mesajı başlatır (S5'teki aç kalma yok).
- Kuyruk kümesinde her uyanışta tek öğe işlendiği için öğe sayısı ile tutamaç sayısı eşit kalır. Hangi tutamacın döndüğü önemsizdir.

## 9. EXTI enjeksiyonu, EXTI testi, ST-LINK posta kutusu

```c
void TIM7_IRQHandler(void)                       /* öncelik 6 < EXTI0 (5) */
{
    TIM7->SR = 0;
    if (g_source != SRC_INJ || !g_started || g_stop_pending) return;
    s_inject_pending = true;
    EXTI->SWIER = 1u << 0;                       /* EXTI0 hemen araya girer -> t0 */
    arm_ms(INJ_MIN_MS + (rnd() % INJ_SPAN_MS));  /* 0,5–0,9 s sonra tekrar */
}
```

EXTI0 ISR'ında t₀ yine ilk komutta alınır. Enjekte kenar, pin seviyesine bakılmadan basış sayılır; sonrası fiziksel basışla aynıdır.

**EXTI testi:** UartTxTask, ölçüm dışında 100 kez `EXTI->SWIER` yazar. ISR'daki ilk ölçüm anı ile arasındaki farkı DWT çevrim sayacıyla ölçer. Ölçülen değer 63 çevrim ≈ 375 ns, en fazla 95 çevrim ≈ 565 ns'dir. Bu, t₀'ın önündeki kesme giriş gecikmesidir.

**Posta kutusu:** `__attribute__((section(".mailbox"))) volatile dbg_mailbox_t g_mailbox;` linker'da 0x20000000'a sabitlenmiştir (NOLOAD). PC metni yazar, sonra seq'i yazar. `mailbox_poll()` seq değişince komutu `handle_cmd()`'e verir.

## 10. PC tarafı
`interface/uart_monitor/`:
- `link.py`: ayrı iş parçacığında okuma yapar; satırlar toplu sinyalle gelir.
- `protocol.py`: satır çözücü.
- `session.py`: SCN → START → STOP → DUMP durum makinesi ve CSV yazımı.
- `metrics.py`: mod 2³² farklar ve özet. Analiz betikleri de aynı modülü kullanır.
- `control.py`: komut kanalı; UART veya ST-LINK posta kutusu, otomatik seçim.
- `runner.py`: başlıksız deney yürütücüsü (varyant × senaryo matrisi).
- `views.py` / `gui.py`: "Yanıt Süresi Laboratuvarı" arayüzü.
  - Sol kenar çubuğu: bağlantı, deney planı (senaryo + hat/CPU doluluğu, varyant kartları, uyarım, olay sayısı), kart durumu.
  - Sağ alan: gecikme zinciri, olay şeridi, istatistik şeridi; R ve kümülatif dağılım, aşamalar, olay tablosu, varyant ısı matrisi ve canlı TX kuyruğu sekmeleri.
  - Arayüz 100 ms'de bir güncellenir; TEL satırları ham görünüme yazılmaz.
