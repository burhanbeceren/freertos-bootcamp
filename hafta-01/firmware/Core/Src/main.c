/**
 * @file main.c
 * @brief Donanım başlatma (168 MHz, GPIO, USART2 + DMA, TIM2) ve scheduler başlatma.
 *
 * Uygulama mantığı App/ altındadır. Bu dosya CubeMX çıktısına benzer şekilde
 * elle yazılmıştır; ayarlar hafta-01/docs/setup.md içinde tablolanmıştır.
 */
#include "main.h"
#include "FreeRTOS.h"
#include "task.h"
#include "app.h"
#include "app_config.h"
#include "timebase.h"
#include "work.h"
#include "adc_temp.h"

UART_HandleTypeDef huart2;
DMA_HandleTypeDef  hdma_usart2_tx;

static void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_DMA_Init(void);
static void MX_USART2_UART_Init(void);

int main(void)
{
    HAL_Init();                 /* Flash prefetch + I/D cache açık, NVIC grup 4 (MspInit) */
    SystemClock_Config();       /* 168 MHz */

    MX_GPIO_Init();
    MX_DMA_Init();
    MX_USART2_UART_Init();

    timebase_init();            /* TIM2 = 1 MHz zaman damgası */
    work_calibrate();           /* S4/S5 CPU işi için iterasyon/ms */
    adc_temp_init();            /* TEL: sıcaklık + VDDA */

    app_init();                 /* kuyruklar + 3 görev */

    HAL_GPIO_WritePin(LED_PORT, LED_GREEN_PIN, GPIO_PIN_SET);
    vTaskStartScheduler();

    Error_Handler();            /* buraya dönülmemeli (heap yetersiz) */
    for (;;) { }
}

/* HSE 8 MHz -> PLL (M=8, N=336, P=2, Q=7) -> SYSCLK 168 MHz, AHB 168, APB1 42, APB2 84 */
static void SystemClock_Config(void)
{
    RCC_OscInitTypeDef osc = {0};
    RCC_ClkInitTypeDef clk = {0};

    __HAL_RCC_PWR_CLK_ENABLE();
    __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);

    osc.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    osc.HSEState       = RCC_HSE_ON;
    osc.PLL.PLLState   = RCC_PLL_ON;
    osc.PLL.PLLSource  = RCC_PLLSOURCE_HSE;
    osc.PLL.PLLM       = 8;
    osc.PLL.PLLN       = 336;
    osc.PLL.PLLP       = RCC_PLLP_DIV2;
    osc.PLL.PLLQ       = 7;
    if (HAL_RCC_OscConfig(&osc) != HAL_OK) {
        Error_Handler();
    }

    clk.ClockType      = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK |
                         RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    clk.SYSCLKSource   = RCC_SYSCLKSOURCE_PLLCLK;
    clk.AHBCLKDivider  = RCC_SYSCLK_DIV1;
    clk.APB1CLKDivider = RCC_HCLK_DIV4;
    clk.APB2CLKDivider = RCC_HCLK_DIV2;
    if (HAL_RCC_ClockConfig(&clk, FLASH_LATENCY_5) != HAL_OK) {
        Error_Handler();
    }
}

static void MX_GPIO_Init(void)
{
    GPIO_InitTypeDef g = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOD_CLK_ENABLE();
    __HAL_RCC_GPIOE_CLK_ENABLE();

    /* LED'ler */
    HAL_GPIO_WritePin(LED_PORT, LED_GREEN_PIN | LED_ORANGE_PIN | LED_RED_PIN | LED_BLUE_PIN,
                      GPIO_PIN_RESET);
    g.Pin   = LED_GREEN_PIN | LED_ORANGE_PIN | LED_RED_PIN | LED_BLUE_PIN;
    g.Mode  = GPIO_MODE_OUTPUT_PP;
    g.Pull  = GPIO_NOPULL;
    g.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(LED_PORT, &g);

    /* B1 = PA0, kart üzerinde harici pull-down + RC var. İki kenar: bkz. button.c */
    g.Pin  = GPIO_PIN_0;
    g.Mode = GPIO_MODE_IT_RISING_FALLING;
    g.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(GPIOA, &g);
    /* PE7 = deney kontrol butonu (diğer ucu GND), dahili pull-up, iki kenar. */
    g.Pin  = GPIO_PIN_7;
    g.Mode = GPIO_MODE_IT_RISING_FALLING;
    g.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(GPIOE, &g);
    /* NVIC'ler, kuyruklar kurulduktan sonra app_init() içinde açılır. */
}

static void MX_DMA_Init(void)
{
    __HAL_RCC_DMA1_CLK_ENABLE();
    HAL_NVIC_SetPriority(DMA1_Stream6_IRQn, 6, 0);
    HAL_NVIC_EnableIRQ(DMA1_Stream6_IRQn);
}

static void MX_USART2_UART_Init(void)
{
    huart2.Instance          = USART2;
    huart2.Init.BaudRate     = UART_BAUD;
    huart2.Init.WordLength   = UART_WORDLENGTH_8B;
    huart2.Init.StopBits     = UART_STOPBITS_1;
    huart2.Init.Parity       = UART_PARITY_NONE;
    huart2.Init.Mode         = UART_MODE_TX_RX;
    huart2.Init.HwFlowCtl    = UART_HWCONTROL_NONE;
    huart2.Init.OverSampling = UART_OVERSAMPLING_16;
    if (HAL_UART_Init(&huart2) != HAL_OK) {
        Error_Handler();
    }
}

/* FreeRTOS kancaları */
void vApplicationStackOverflowHook(TaskHandle_t task, char *name)
{
    (void)task;
    (void)name;
    Error_Handler();
}

void vApplicationMallocFailedHook(void)
{
    Error_Handler();
}

void Error_Handler(void)
{
    __disable_irq();
    HAL_GPIO_WritePin(LED_PORT, LED_RED_PIN, GPIO_PIN_SET);
    for (;;) { }
}
