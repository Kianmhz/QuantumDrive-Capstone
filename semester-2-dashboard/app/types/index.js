/**
 * @typedef {Object} DeviceStatus
 * @property {boolean} online
 * @property {boolean} running
 * @property {string} name
 */

/**
 * @typedef {Object} DeviceState
 * @property {'pc' | 'pi'} id
 * @property {string} label
 * @property {string} icon
 * @property {boolean | null} online   - null = unknown (not yet fetched)
 * @property {boolean | null} running
 * @property {boolean} loading         - true while an action is in-flight
 * @property {string | null} error
 */

/**
 * @typedef {Object} LogEntry
 * @property {string} id
 * @property {Date} timestamp
 * @property {string} message
 * @property {'info' | 'success' | 'error' | 'warning'} type
 */

export {}
