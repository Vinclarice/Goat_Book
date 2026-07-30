import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { DevUiGallery } from "./DevUiGallery";

describe("DevUiGallery", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  it("renders every button variant and the switch and card samples", () => {
    render(<DevUiGallery />);

    for (const variant of ["default", "outline", "secondary", "ghost", "destructive", "link"]) {
      expect(screen.getAllByRole("button", { name: variant }).length).toBeGreaterThan(0);
    }
    expect(screen.getByRole("switch")).toBeInTheDocument();
    expect(screen.getByText("Renew passport")).toBeInTheDocument();
  });

  it("applies the chosen theme to the document root and persists it", async () => {
    const user = userEvent.setup();
    render(<DevUiGallery />);

    await user.click(screen.getByRole("button", { name: "Dark" }));
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(localStorage.getItem("clarice-theme")).toBe("dark");

    await user.click(screen.getByRole("button", { name: "System" }));
    expect(localStorage.getItem("clarice-theme")).toBeNull();
  });
});
