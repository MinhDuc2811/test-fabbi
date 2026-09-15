import { test, expect, type Browser } from "@playwright/test";

function uniqueEmail(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 100000)}@example.com`;
}

async function registerAndLogin(browser: Browser, email: string, password: string) {
  const context = await browser.newContext();
  const page = await context.newPage();

  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm Password").fill(password);
  await page.getByRole("button", { name: "Create Account" }).click();
  await expect(page).toHaveURL("/");

  return { context, page };
}

test("cross-user data isolation: user B cannot see user A's private todo", async ({
  browser,
}) => {
  const password = "Password@123";
  const privateTitle = `A's private todo ${Date.now()}`;

  // User A creates a private todo in its own isolated browser context.
  const userA = await registerAndLogin(browser, uniqueEmail("isolation-a"), password);
  await userA.page.getByRole("button", { name: "Add Todo" }).click();
  await userA.page.getByLabel("Title").fill(privateTitle);
  await userA.page.getByRole("button", { name: "Create" }).click();
  await expect(userA.page.getByText(privateTitle)).toBeVisible();

  // User B, in a completely separate context (no shared localStorage/cookies),
  // must never see user A's todo - neither via a cross-user IDOR nor via a
  // cache entry keyed the same for both users.
  const userB = await registerAndLogin(browser, uniqueEmail("isolation-b"), password);
  await expect(userB.page.getByText(privateTitle)).not.toBeVisible();
  await expect(userB.page.getByText("No todos yet")).toBeVisible();

  await userA.context.close();
  await userB.context.close();
});

test("cross-user isolation persists after logout/login on the same browser", async ({
  browser,
}) => {
  const password = "Password@123";
  const privateTitle = `Same-browser secret ${Date.now()}`;

  const context = await browser.newContext();
  const page = await context.newPage();

  const emailA = uniqueEmail("same-browser-a");
  await page.goto("/register");
  await page.getByLabel("Email").fill(emailA);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm Password").fill(password);
  await page.getByRole("button", { name: "Create Account" }).click();
  await expect(page).toHaveURL("/");

  await page.getByRole("button", { name: "Add Todo" }).click();
  await page.getByLabel("Title").fill(privateTitle);
  await page.getByRole("button", { name: "Create" }).click();
  await expect(page.getByText(privateTitle)).toBeVisible();

  await page.getByRole("button", { name: "Logout" }).click();
  await expect(page).toHaveURL(/\/login$/);

  // A second user logs in on the SAME browser context (same localStorage /
  // in-memory React Query cache) right after. Without clearing the query
  // cache on logout, this can briefly render user A's cached todo list.
  const emailB = uniqueEmail("same-browser-b");
  await page.getByRole("link", { name: "Sign up" }).click();
  // Wait for the client-side route transition to finish before filling the
  // form - filling immediately after click() can race the React Router
  // navigation and land on the about-to-unmount /login page's field.
  await expect(page).toHaveURL(/\/register$/);
  await page.getByLabel("Email").fill(emailB);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm Password").fill(password);
  await page.getByRole("button", { name: "Create Account" }).click();
  await expect(page).toHaveURL("/");

  await expect(page.getByText(privateTitle)).not.toBeVisible();
  await expect(page.getByText("No todos yet")).toBeVisible();

  await context.close();
});
