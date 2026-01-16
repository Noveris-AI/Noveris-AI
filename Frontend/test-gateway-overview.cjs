const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Capture API responses
  page.on('response', async response => {
    if (response.url().includes('/api/gateway/overview')) {
      console.log('\n=== Gateway Overview API Response ===');
      console.log('Status:', response.status());
      try {
        const data = await response.json();
        console.log('Data:', JSON.stringify(data, null, 2));
      } catch (e) {
        console.log('Could not parse response');
      }
    }
  });

  console.log('=== Testing Gateway Overview Page ===\n');

  try {
    // Navigate to homepage first
    console.log('1. Loading homepage...');
    await page.goto('http://localhost:3001', { waitUntil: 'networkidle', timeout: 30000 });
    console.log('   URL:', page.url());

    // Navigate to Gateway page
    console.log('\n2. Navigating to Gateway page...');
    await page.click('text=模型转发');
    await page.waitForTimeout(3000);
    console.log('   URL:', page.url());

    // Take screenshot
    await page.screenshot({ path: '/tmp/gateway-overview-test.png', fullPage: true });
    console.log('\n3. Screenshot saved to /tmp/gateway-overview-test.png');

    // Check for error message
    const errorElement = await page.$('.text-red-500, .text-destructive, [class*="error"]');
    if (errorElement) {
      const errorText = await errorElement.textContent();
      console.log('\n   Error message found:', errorText);
    } else {
      console.log('\n   No error message - page loaded successfully!');
    }

    // Wait for inspection
    console.log('\n4. Browser will stay open for 10 seconds...');
    await page.waitForTimeout(10000);

  } catch (error) {
    console.error('Error:', error.message);
    await page.screenshot({ path: '/tmp/gateway-error.png', fullPage: true });
  } finally {
    await browser.close();
  }
})();
