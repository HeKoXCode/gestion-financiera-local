(() => {
    const nav = document.querySelector(".main-nav");
    const activeLink = nav?.querySelector(".nav-link.is-active");
    const compactNavigation = window.matchMedia("(max-width: 58rem)");

    if (!nav || !activeLink || !compactNavigation.matches) return;

    const navBox = nav.getBoundingClientRect();
    const activeBox = activeLink.getBoundingClientRect();
    const isOutsideView = activeBox.left < navBox.left || activeBox.right > navBox.right;

    if (isOutsideView) {
        activeLink.scrollIntoView({behavior: "auto", block: "nearest", inline: "center"});
    }
})();
