import { ref, watch } from 'vue'

const theme = ref(localStorage.getItem('dashboardTheme') || 'light')

const isDark = () => theme.value === 'dark'

const setTheme = (newTheme) => {
  theme.value = newTheme
  localStorage.setItem('dashboardTheme', newTheme)
  
  if (newTheme === 'dark') {
    document.documentElement.classList.add('dark')
    document.body.classList.add('dark-theme')
  } else {
    document.documentElement.classList.remove('dark')
    document.body.classList.remove('dark-theme')
  }
}

const toggleTheme = () => {
  setTheme(theme.value === 'light' ? 'dark' : 'light')
}

const initTheme = () => {
  const savedTheme = localStorage.getItem('dashboardTheme')
  if (savedTheme) {
    setTheme(savedTheme)
  }
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
