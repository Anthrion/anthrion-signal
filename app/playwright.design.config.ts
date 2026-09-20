import { defineConfig } from '@playwright/test'
import config from './playwright.config'

export default defineConfig({ ...config, testDir: './design', projects: [config.projects![0]] })
