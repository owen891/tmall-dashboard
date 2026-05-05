import { ref, computed, watch } from 'vue'

const VALID_THEMES = ['light', 'dark', 'auto']

const theme = ref(localStorage.getItem('dashboardTheme') || 'light')

const prefersDark = () => {
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

const isDark = computed(() => {
  if (theme.value === 'auto') return prefersDark()
  return theme.value === 'dark'
})

const setTheme = (newTheme) => {
  if (!VALID_THEMES.includes(newTheme)) {
    console.warn(`Invalid theme: ${newTheme}, falling back to 'light'`)
    newTheme = 'light'
  }
  theme.value = newTheme
  localStorage.setItem('dashboardTheme', newTheme)
  applyTheme()
}

const applyTheme = () => {
  const dark = isDark.value
  if (dark) {
    document.documentElement.classList.add('dark')
    document.body.classList.add('dark-theme')
  } else {
    document.documentElement.classList.remove('dark')
    document.body.classList.remove('dark-theme')
  }
}

const toggleTheme = () => {
  const themes = ['light', 'dark', 'auto']
  const currentIndex = themes.indexOf(theme.value)
  const nextIndex = (currentIndex + 1) % themes.length
  setTheme(themes[nextIndex])
}

const initTheme = () => {
  applyTheme()
  
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (theme.value === 'auto') {
      applyTheme()
    }
  })
}

if (typeof window !== 'undefined') {
  applyTheme()
}

export function useTheme() {
  return {
    theme,
    isDark,
    setTheme,
    toggleTheme,
    initTheme
  }
}
