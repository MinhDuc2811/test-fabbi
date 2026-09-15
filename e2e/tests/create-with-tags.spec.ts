import { test, expect } from "@playwright/test";

function uniqueEmail(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 100000)}@example.com`;
}

test("can select tags while creating a todo", async ({ page }) => {
  const email = uniqueEmail("create-tags");
  const password = "Password@123";
  const title = `Groceries ${Date.now()}`;

  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm Password").fill(password);
  await page.getByRole("button", { name: "Create Account" }).click();
  await expect(page).toHaveURL("/");

  await page.getByRole("button", { name: "Manage Tags" }).click();
  const tagManagerDialog = page.getByRole("dialog");
  await tagManagerDialog.getByPlaceholder("New tag name").fill("Home");
  await tagManagerDialog.getByRole("button", { name: "Add" }).click();
  await expect(tagManagerDialog.getByText("Home", { exact: true })).toBeVisible();
  await page.keyboard.press("Escape");

  await page.getByRole("button", { name: "Add Todo" }).click();
  const createDialog = page.getByRole("dialog");
  await expect(createDialog.getByRole("heading", { name: "Create Todo" })).toBeVisible();
  await createDialog.getByLabel("Title").fill(title);
  await createDialog.getByText("Home", { exact: true }).click();
  await createDialog.getByRole("button", { name: "Create" }).click();

  const row = page.locator("div.group", { hasText: title });
  await expect(row.getByText("Home")).toBeVisible();
  await page.screenshot({ path: "test-results/manual-create-with-tag.png" });
});
