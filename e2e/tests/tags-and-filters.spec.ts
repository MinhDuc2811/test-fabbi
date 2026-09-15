import { test, expect } from "@playwright/test";

function uniqueEmail(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 100000)}@example.com`;
}

test("tag management, attaching tags, filtering, and bulk actions", async ({ page }) => {
  const email = uniqueEmail("tier4");
  const password = "Password@123";
  const stamp = Date.now();
  const taggedTitle = `Alpha ${stamp}`;
  const plainTitle = `Beta ${stamp}`;

  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm Password").fill(password);
  await page.getByRole("button", { name: "Create Account" }).click();
  await expect(page).toHaveURL("/");

  // Create a tag via Tag Manager.
  await page.getByRole("button", { name: "Manage Tags" }).click();
  const tagManagerDialog = page.getByRole("dialog");
  await tagManagerDialog.getByPlaceholder("New tag name").fill("Urgent");
  await tagManagerDialog.getByRole("button", { name: "Add" }).click();
  await expect(tagManagerDialog.getByText("Urgent", { exact: true })).toBeVisible();
  await page.keyboard.press("Escape");

  // Create two todos with unambiguous, non-overlapping titles.
  await page.getByRole("button", { name: "Add Todo" }).click();
  await page.getByLabel("Title").fill(taggedTitle);
  await page.getByRole("button", { name: "Create" }).click();
  await expect(page.getByText(taggedTitle)).toBeVisible();

  await page.getByRole("button", { name: "Add Todo" }).click();
  await page.getByLabel("Title").fill(plainTitle);
  await page.getByRole("button", { name: "Create" }).click();
  await expect(page.getByText(plainTitle)).toBeVisible();

  // Attach the tag to exactly the "Alpha" todo via its edit dialog.
  const taggedRow = page.locator("div.group", { hasText: taggedTitle });
  await expect(taggedRow).toHaveCount(1);
  await taggedRow.getByRole("button").nth(0).click(); // pencil (edit)
  const editDialog = page.getByRole("dialog");
  await expect(editDialog.getByRole("heading", { name: "Edit Todo" })).toBeVisible();
  await editDialog.getByText("Urgent", { exact: true }).click();
  // Wait for the attach mutation to invalidate and refetch the todo list
  // before closing the dialog.
  await expect(page.locator("div.group", { hasText: taggedTitle }).getByText("Urgent")).toBeVisible();
  await page.keyboard.press("Escape");

  await page.screenshot({ path: "test-results/manual-tag-on-todo.png" });

  // Filter by tag - only the tagged ("Alpha") todo should show.
  await page.locator("select").nth(1).selectOption({ label: "Urgent" });
  await expect(page.getByText(taggedTitle)).toBeVisible();
  await expect(page.getByText(plainTitle)).not.toBeVisible();
  await page.screenshot({ path: "test-results/manual-filter-by-tag.png" });

  // Clear filters.
  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(page.getByText(plainTitle)).toBeVisible();

  // Bulk actions: select both todos, mark complete.
  const checkboxes = page.getByRole("checkbox");
  const count = await checkboxes.count();
  // Each row renders 2 checkboxes (select + complete); 2 items = 4 total.
  expect(count).toBeGreaterThanOrEqual(4);
  await checkboxes.nth(0).click();
  await checkboxes.nth(2).click();

  await expect(page.getByText("2 selected")).toBeVisible();
  await page.screenshot({ path: "test-results/manual-bulk-select.png" });
  await page.getByRole("button", { name: "Mark complete" }).click();

  await expect(page.getByText("2 selected")).not.toBeVisible();

  // Filter by status=completed - both should still show.
  await page.locator("select").nth(0).selectOption({ label: "Completed" });
  await expect(page.getByText(taggedTitle)).toBeVisible();
  await expect(page.getByText(plainTitle)).toBeVisible();
  await page.screenshot({ path: "test-results/manual-filter-by-status.png" });
});
