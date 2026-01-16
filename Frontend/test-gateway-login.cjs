const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Capture API responses
  page.on('response', async response => {
    if (response.url().includes('/api/')) {
      const status = response.status();
      const url = response.url();
      console.log(`API: ${url} => ${status}`);
      if (status >= 400) {
        try {
          const data = await response.json();
          console.log('  Error:', JSON.stringify(data));
        } catch (e) {}
      }
    }
  });

  console.log('=== Testing Gateway Overview with Login ===\n');

  try {
    // 1. Navigate to login page
    console.log('1. Navigating to login page...');
    await page.goto('http://localhost:3001/login', { waitUntil: 'networkidle', timeout: 30000 });
    console.log('   URL:', page.url());
    await page.waitForTimeout(1000);

    // 2. Fill login form
    console.log('\n2. Logging in...');
    const emailInput = await page.$('input[type="email"], input[name="email"]');
    const passwordInput = await page.$('input[type="password"]');

    if (emailInput && passwordInput) {
      await emailInput.fill('demo@noveris.com');
      await passwordInput.fill('Test123456');

      // Click login button
      const submitBtn = await page.$('button[type="submit"]');
      if (submitBtn) {
        await submitBtn.click();
        console.log('   Login submitted');
        await page.waitForTimeout(3000);
        console.log('   URL after login:', page.url());
      }
    } else {
      console.log('   Already logged in or login form not found');
    }

    // 3. Navigate to Gateway page
    console.log('\n3. Navigating to Gateway page...');
    await page.click('text=模型转发');
    await page.waitForTimeout(3000);
    console.log('   URL:', page.url());

    // Take screenshot
    await page.screenshot({ path: '/tmp/gateway-with-login.png', fullPage: true });
    console.log('\n4. Screenshot saved to /tmp/gateway-with-login.png');

    // Check for error messages
    const pageText = await page.textContent('body');
    if (pageText.includes('加载数据失败')) {
      console.log('\n   ERROR: Data loading still failed');
    } else {
      console.log('\n   SUCCESS: No error message found');
    }

    // Wait for inspection
    console.log('\n5. Browser will stay open for 10 seconds...');
    await page.waitForTimeout(10000);

  } catch (error) {
    console.error('Error:', error.message);
    await page.screenshot({ path: '/tmp/gateway-error.png', fullPage: true });
  } finally {
    await browser.close();
  }
})();
