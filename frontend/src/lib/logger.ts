// frontend/src/lib/logger.ts
// 条件日志：生产环境静默，开发环境输出

const isDev = import.meta.env.DEV

export const log = isDev ? console.log.bind(console) : () => {}
export const warn = isDev ? console.warn.bind(console) : () => {}
export const error = isDev ? console.error.bind(console) : () => {}
