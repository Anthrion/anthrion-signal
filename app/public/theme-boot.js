// Applies the saved theme before the first paint, so a light-theme visit never flashes dark.
// Loaded as a same-origin file because the page's security policy forbids inline scripts.
try {
  var preferences = JSON.parse(localStorage.getItem('anthrion-preferences-v1') || 'null')
  if (preferences && preferences.theme === 'light') {
    document.documentElement.dataset.theme = 'light'
    document.documentElement.style.colorScheme = 'light'
    var meta = document.querySelector('meta[name="theme-color"]')
    if (meta) meta.setAttribute('content', '#f2f4f3')
  }
} catch (error) {
  /* Storage can be unavailable; the page then opens in its default dark theme. */
}
