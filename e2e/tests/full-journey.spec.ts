import { test, expect } from "@playwright/test";

function uniqueEmail(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 100000)}@example.com`;
}

test("full user journey: register -> create todo -> toggle -> verify -> logout", async ({
  page,
}) => {
  const email = uniqueEmail("journey");
  const password = "Password@123";
  const todoTitle = `Buy milk ${Date.now()}`;

  // Register
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm Password").fill(password);
  await page.getByRole("button", { name: "Create Account" }).click();

  await expect(page).toHaveURL("/");
  await expect(page.getByText(email)).toBeVisible();

  // Create a todo
  await page.getByRole("button", { name: "Add Todo" }).click();
  await page.getByLabel("Title").fill(todoTitle);
  await page.getByRole("button", { name: "Create" }).click();

  await expect(page.getByText(todoTitle)).toBeVisible();

  // The completion checkbox is associated with the todo title via
  // <label htmlFor>; exact:true is required to disambiguate it from the
  // Tier 4 bulk-select checkbox, whose aria-label ("Select <title>") also
  // contains the title as a substring.
  const checkbox = page.getByLabel(todoTitle, { exact: true });

  // Toggle completion on -> off, verify it persists both ways (partial-update/
  // falsy-boolean bug: a naive fix would drop the "uncheck" transition).
  await checkbox.click();
  await expect(checkbox).toBeChecked();
  await page.reload();
  await expect(page.getByLabel(todoTitle, { exact: true })).toBeChecked();

  await page.getByLabel(todoTitle, { exact: true }).click();
  await expect(page.getByLabel(todoTitle, { exact: true })).not.toBeChecked();
  await page.reload();
  await expect(page.getByLabel(todoTitle, { exact: true })).not.toBeChecked();

  // Logout
  await page.getByRole("button", { name: "Logout" }).click();
  await expect(page).toHaveURL(/\/login$/);
});
