const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false, devtools: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Enable request interception to see all requests
  await page.route('**/*', async (route) => {
    const request = route.request();
    if (request.url().includes('gateway/overview') || request.url().includes('localhost:8000')) {
      console.log(`\n>>> REQUEST: ${request.method()} ${request.url()}`);
      console.log('    Headers:', JSON.stringify(request.headers(), null, 2));
    }
    await route.continue();
  });

  // Log all responses
  page.on('response', async (response) => {
    const url = response.url();
    if (url.includes('gateway') || url.includes('localhost:8000')) {
      console.log(`\n<<< RESPONSE: ${response.status()} ${url}`);
      try {
        const text = await response.text();
        console.log('    Body:', text.substring(0, 500));
      } catch (e) {}
    }
  });

  // Log console messages
  page.on('console', msg => {
    if (msg.type() === 'error' || msg.text().includes('gateway') || msg.text().includes('CORS')) {
      console.log(`CONSOLE [${msg.type()}]:`, msg.text());
    }
  });

  // Log request failures
  page.on('requestfailed', request => {
    console.log(`\n!!! REQUEST FAILED: ${request.url()}`);
    console.log('    Failure:', request.failure()?.errorText);
  });

  console.log('=== Debug Gateway API Call ===\n');

  try {
    // Navigate directly to gateway page
    console.log('1. Navigating to gateway page...');
    await page.goto('http://localhost:3001/dashboard/forwarding', { waitUntil: 'networkidle', timeout: 30000 });
    console.log('   URL:', page.url());

    // Wait for potential API calls
    console.log('\n2. Waiting for API calls...');
    await page.waitForTimeout(5000);

    // Take screenshot
    await page.screenshot({ path: '/tmp/gateway-debug.png', fullPage: true });
    console.log('\n3. Screenshot saved');

    // Keep browser open
    console.log('\n4. Browser stays open for 15 seconds...');
    await page.waitForTimeout(15000);

  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await browser.close();
  }
})();
