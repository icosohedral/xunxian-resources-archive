const searchInput = document.querySelector("[data-search-input]");
const copyButton = document.querySelector("[data-copy-link]");
const directoryPanel = document.querySelector(".index-rail");
const todayVisitors = document.getElementById("today-visitors");
const aboutOpenButton = document.querySelector("[data-about-open]");
const aboutDialog = document.querySelector("[data-about-dialog]");
const aboutCloseButton = document.querySelector("[data-about-close]");
let directoryRequestId = 0;

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

aboutOpenButton?.addEventListener("click", () => {
  if (aboutDialog instanceof HTMLDialogElement && !aboutDialog.open) {
    aboutDialog.showModal();
    aboutCloseButton?.focus();
  }
});

aboutCloseButton?.addEventListener("click", () => {
  if (aboutDialog instanceof HTMLDialogElement) {
    aboutDialog.close();
    aboutOpenButton?.focus();
  }
});

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
    aboutDialog.close();
    aboutOpenButton?.focus();
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

copyButton?.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(window.location.href);
    copyButton.textContent = "链接已复制";
    window.setTimeout(() => {
      copyButton.textContent = "复制本页链接";
    }, 1800);
  } catch {
    copyButton.textContent = "请复制地址栏链接";
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
  directoryScrollTop:
    directoryPanel?.querySelector(".resource-list")?.scrollTop ?? 0,
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
    const selectors = [".result-caption", ".resource-list", ".pagination"];
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
    const nextResourceList = directoryPanel.querySelector(".resource-list");
    if (nextResourceList) {
      nextResourceList.scrollTop = preservedPosition.directoryScrollTop;
    }
    markCurrentResource();

    if (updateHistory) {
      const visibleUrl = new URL(window.location.href);
      visibleUrl.search = targetUrl.search;
      window.history.pushState(
        { directoryPagination: true },
        "",
        `${visibleUrl.pathname}${visibleUrl.search}${visibleUrl.hash}`,
      );
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
