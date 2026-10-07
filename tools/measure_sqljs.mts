import { chromium } from 'playwright-core';

async function main() {
  const browser = await chromium.launch({
    headless: true
  });
  
  const page = await browser.newPage();
  
  page.on('console', msg => console.log('PAGE LOG:', msg.text()));

  // Inject a script before navigation to measure long tasks
  await page.addInitScript(() => {
    window.longTasks = [];
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        window.longTasks.push({
          duration: entry.duration,
          startTime: entry.startTime,
          name: entry.name
        });
      }
    });
    observer.observe({ entryTypes: ['longtask'] });
  });

  await page.goto('http://localhost:5174/');
  
  await page.waitForFunction(() => (window as any).bootTiming !== undefined, { timeout: 15000 });
  
  const bootTiming = await page.evaluate(() => (window as any).bootTiming);
  const longTasks = await page.evaluate(() => (window as any).longTasks);
  
  console.log('Boot Timing:', bootTiming);
  
  let totalBlocking = 0;
  let maxBlock = 0;
  for (const task of longTasks) {
    totalBlocking += task.duration;
    if (task.duration > maxBlock) maxBlock = task.duration;
  }
  
  console.log(`Main thread long tasks: ${longTasks.length} tasks`);
  console.log(`Max blocking time: ${maxBlock.toFixed(2)}ms`);
  console.log(`Total blocking time: ${totalBlocking.toFixed(2)}ms`);

  await browser.close();
}

main().catch(console.error);
