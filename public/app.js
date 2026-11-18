const searchInput = document.querySelector("[data-search-input]");
const directoryPanel = document.querySelector(".index-rail");
const todayVisitors = document.getElementById("today-visitors");
const aboutOpenButtons = document.querySelectorAll("[data-about-open]");
const aboutDialog = document.querySelector("[data-about-dialog]");
const aboutCloseButton = document.querySelector("[data-about-close]");
let directoryRequestId = 0;
let aboutReturnFocus = null;

const recordAnonymousVisit = async () => {
  if (!todayVisitors) {
    return;
  }
  try {
    const storageKey = "xunxian-resources-anonymous-visitor";
    let visitorId = localStorage.getItem(storageKey);
    if (!visitorId) {
      visitorId =
        globalThis.crypto?.randomUUID?.() ||
        `${Date.now().toString(36)}_${Math.random().toString(36).slice(2)}`;
      localStorage.setItem(storageKey, visitorId);
    }
    const response = await fetch("/api/visit", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ visitor_id: visitorId }),
      keepalive: true,
    });
    if (!response.ok) {
      return;
    }
    const data = await response.json();
    if (Number.isInteger(data.count)) {
      todayVisitors.textContent = String(data.count);
    }
  } catch {
    // 禁用本地存储的浏览器不参与统计，避免重复刷新放大数字。
  }
};

recordAnonymousVisit();

const closeAboutDialog = () => {
  if (aboutDialog instanceof HTMLDialogElement && aboutDialog.open) {
    aboutDialog.close();
  }
};

aboutOpenButtons.forEach((button) => {
  button.addEventListener("click", () => {
    if (aboutDialog instanceof HTMLDialogElement && !aboutDialog.open) {
      aboutReturnFocus = button;
      aboutDialog.showModal();
      aboutCloseButton?.focus({ preventScroll: true });
    }
  });
});

// Esc 关闭、点“知道了”或点遮罩关闭后，焦点都回到打开弹窗的按钮
aboutDialog?.addEventListener("close", () => {
  aboutReturnFocus?.focus({ preventScroll: true });
  aboutReturnFocus = null;
});

aboutCloseButton?.addEventListener("click", closeAboutDialog);

aboutDialog?.addEventListener("click", (event) => {
  if (!(aboutDialog instanceof HTMLDialogElement) || event.target !== aboutDialog) {
    return;
  }
  const panel = aboutDialog.querySelector(".about-panel");
  if (!(panel instanceof HTMLElement)) {
    return;
  }
  const bounds = panel.getBoundingClientRect();
  const outsidePanel =
    event.clientX < bounds.left ||
    event.clientX > bounds.right ||
    event.clientY < bounds.top ||
    event.clientY > bounds.bottom;
  if (outsidePanel) {
    closeAboutDialog();
  }
});

if ("scrollRestoration" in window.history) {
  window.history.scrollRestoration = "manual";
}

document.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    searchInput?.focus();
  }
});


const markCurrentResource = () => {
  if (!directoryPanel || !window.location.pathname.startsWith("/resources/")) {
    return;
  }
  directoryPanel.querySelectorAll(".resource-list > a").forEach((link) => {
    const linkUrl = new URL(link.href, window.location.href);
    link.classList.toggle(
      "is-current",
      linkUrl.pathname === window.location.pathname,
    );
  });
};

const currentDirectoryPosition = () => ({
  viewportScrollX: window.scrollX,
  viewportScrollY: window.scrollY,
});

const refreshDirectory = async (
  url,
  {
    updateHistory = true,
    preservedPosition = currentDirectoryPosition(),
  } = {},
) => {
  if (!directoryPanel) {
    return;
  }

  const requestId = ++directoryRequestId;
  const targetUrl = new URL(url, window.location.href);
  directoryPanel.setAttribute("aria-busy", "true");

  try {
    const response = await fetch(targetUrl, {
      headers: { "X-Requested-With": "directory-pagination" },
    });
    if (!response.ok) {
      throw new Error(`目录加载失败：${response.status}`);
    }

    const documentText = await response.text();
    const nextDocument = new DOMParser().parseFromString(documentText, "text/html");
    // 翻页按钮位于结果栏内，替换结果栏即可同时更新页码
    const selectors = [".result-caption", ".resource-list"];
    const replacements = selectors.map((selector) => [
      directoryPanel.querySelector(selector),
      nextDocument.querySelector(`.index-rail ${selector}`),
    ]);
    if (replacements.some(([currentNode, nextNode]) => !currentNode || !nextNode)) {
      throw new Error("目录响应缺少必要内容");
    }
    if (requestId !== directoryRequestId) {
      return;
    }

    replacements.forEach(([currentNode, nextNode]) => {
      currentNode.replaceChildren(...nextNode.childNodes);
    });
    const nextPanel = nextDocument.querySelector(".index-rail");
    if (nextPanel instanceof HTMLElement) {
      directoryPanel.dataset.pageSize = nextPanel.dataset.pageSize || "";
      directoryPanel.dataset.page = nextPanel.dataset.page || "";
    }
    // 目录在卡片内部滚动：换页后从新一页的第一条开始显示
    const nextResourceList = directoryPanel.querySelector(".resource-list");
    if (nextResourceList) {
      nextResourceList.scrollTop = 0;
    }
    markCurrentResource();

    if (updateHistory) {
      const visibleUrl = new URL(window.location.href);
      visibleUrl.search = targetUrl.search;
      const visiblePath = `${visibleUrl.pathname}${visibleUrl.search}${visibleUrl.hash}`;
      if (updateHistory === "replace") {
        // 按窗口高度调整条数时不新增历史记录
        window.history.replaceState({ directoryPagination: true }, "", visiblePath);
      } else {
        window.history.pushState({ directoryPagination: true }, "", visiblePath);
      }
    }
    const restoreViewportPosition = () => {
      if (requestId !== directoryRequestId) {
        return;
      }
      const root = document.documentElement;
      const previousScrollBehavior = root.style.scrollBehavior;
      root.style.scrollBehavior = "auto";
      window.scrollTo(
        preservedPosition.viewportScrollX,
        preservedPosition.viewportScrollY,
      );
      root.style.scrollBehavior = previousScrollBehavior;
    };
    restoreViewportPosition();
    window.requestAnimationFrame(() => {
      restoreViewportPosition();
      window.requestAnimationFrame(restoreViewportPosition);
    });
    window.setTimeout(restoreViewportPosition, 50);
  } catch (error) {
    console.error(error);
  } finally {
    if (requestId === directoryRequestId) {
      directoryPanel.removeAttribute("aria-busy");
    }
  }
};

document.addEventListener("click", (event) => {
  const paginationLink =
    event.target instanceof Element
      ? event.target.closest(".pagination a")
      : null;
  if (!paginationLink || !directoryPanel?.contains(paginationLink)) {
    return;
  }
  event.preventDefault();
  if (paginationLink.getAttribute("aria-disabled") === "true") {
    return;
  }
  const preservedPosition = currentDirectoryPosition();
  paginationLink.blur();
  refreshDirectory(paginationLink.href, { preservedPosition });
});

window.addEventListener("popstate", () => {
  refreshDirectory(`/${window.location.search}`, { updateHistory: false });
});

// 配色切换：与 GM 工作台一致的三套主题，选择保存在本机浏览器
// 手机端导航：任务、音乐默认折叠，点“更多”展开或收起。
const railMoreButton = document.querySelector("[data-rail-more]");
if (railMoreButton) {
  const railNav = railMoreButton.closest(".kind-slips");
  railMoreButton.addEventListener("click", () => {
    const expanded = railMoreButton.getAttribute("aria-expanded") !== "true";
    railMoreButton.setAttribute("aria-expanded", String(expanded));
    railNav.classList.toggle("is-expanded", expanded);
  });
}

const themeStorageKey = "xunxian-archive-color-theme";
const themeSwatches = document.querySelectorAll(".theme-swatch");

const currentTheme = () => {
  const root = document.documentElement;
  if (root.dataset.mode === "dark") {
    return "dark";
  }
  return root.dataset.theme === "orange" ? "orange" : "green";
};

const applyTheme = (theme) => {
  const root = document.documentElement;
  if (theme === "orange" || theme === "dark") {
    root.dataset.theme = "orange";
  } else {
    delete root.dataset.theme;
  }
  if (theme === "dark") {
    root.dataset.mode = "dark";
  } else {
    delete root.dataset.mode;
  }
  themeSwatches.forEach((swatch) => {
    swatch.setAttribute(
      "aria-pressed",
      String(swatch.dataset.themeValue === theme),
    );
  });
};

applyTheme(currentTheme());

themeSwatches.forEach((swatch) => {
  swatch.addEventListener("click", () => {
    const theme = swatch.dataset.themeValue || "green";
    applyTheme(theme);
    try {
      localStorage.setItem(themeStorageKey, theme);
    } catch {
      // 无痕模式等环境不能保存时，仅对当前页面生效
    }
  });
});

// 每页条数随窗口高度变化：索引卡片放得下几条，一页就显示几条，目录不滚动。
// 结果写入 Cookie，之后的页面由服务器直接按这个条数输出。
const pageSizeCookie = "xunxian-archive-page-size";
const minPageSize = 4;
const maxPageSize = 40;

// 让目录正好填满卡片：
// - 剩余空间够放大半行，且多放一行时每行压缩不超过 10%，就多放一行并略压低行高；
// - 否则把剩余空白平均分给每一行，让每行略高一点。
const maxRowCompression = 0.1;

const fittingLayout = () => {
  if (
    !directoryPanel ||
    getComputedStyle(directoryPanel).position !== "sticky"
  ) {
    return null; // 窄屏下目录随页面滚动，沿用默认条数与行高
  }
  const list = directoryPanel.querySelector(".resource-list");
  if (!(list instanceof HTMLElement)) {
    return null;
  }
  const style = getComputedStyle(list);
  const baseRowHeight = parseFloat(style.getPropertyValue("--row-base")) || 52;
  const gap = parseFloat(style.rowGap) || 0;
  const available =
    list.clientHeight -
    parseFloat(style.paddingTop) -
    parseFloat(style.paddingBottom);

  let rows = Math.max(1, Math.floor((available + gap) / (baseRowHeight + gap)));
  const leftover = available - (rows * baseRowHeight + (rows - 1) * gap);
  const compressedHeight = (available - rows * gap) / (rows + 1);
  if (
    leftover >= baseRowHeight / 2 &&
    compressedHeight >= baseRowHeight * (1 - maxRowCompression)
  ) {
    rows += 1;
  }
  rows = Math.min(maxPageSize, Math.max(minPageSize, rows));
  const rowHeight = (available - (rows - 1) * gap) / rows;
  return { size: rows, rowHeight };
};

const syncPageSize = () => {
  const list = directoryPanel?.querySelector(".resource-list");
  const layout = fittingLayout();
  if (layout === null) {
    list?.style.removeProperty("--row-height");
    return;
  }
  const { size, rowHeight } = layout;
  // 行高写在目录元素上；翻页只替换目录内容，所以新一页沿用同样的行高
  // 向下取到 0.01px，避免舍入后最后一行超出卡片
  list.style.setProperty("--row-height", `${Math.floor(rowHeight * 100) / 100}px`);
  try {
    document.cookie = `${pageSizeCookie}=${size}; path=/; max-age=31536000; SameSite=Lax`;
  } catch {
    // 无法写入 Cookie 时，仍按当前条数刷新本页
  }
  const currentSize = Number(directoryPanel.dataset.pageSize) || size;
  if (size === currentSize) {
    return;
  }
  // 保持当前页第一条资料仍在新的一页里
  const currentPage = Number(directoryPanel.dataset.page) || 1;
  const firstIndex = (currentPage - 1) * currentSize;
  const targetUrl = new URL(window.location.href);
  const targetPage = Math.floor(firstIndex / size) + 1;
  if (targetPage > 1 || targetUrl.searchParams.has("page")) {
    targetUrl.searchParams.set("page", String(targetPage));
  }
  refreshDirectory(targetUrl.href, { updateHistory: "replace" });
};

let pageSizeTimer = 0;
syncPageSize();
window.addEventListener("resize", () => {
  window.clearTimeout(pageSizeTimer);
  pageSizeTimer = window.setTimeout(syncPageSize, 200);
});
