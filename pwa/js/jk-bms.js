/**
 * JK-BMS BLE Protocol Handler
 *
 * Supports JK-B series BMS (HW version >= 6) over Web Bluetooth.
 * Protocol: 20-byte request frames, ~300-byte assembled response frames.
 *
 * Service UUID:        0000ffe0-0000-1000-8000-00805f9b34fb
 * Characteristic UUID: 0000ffe1-0000-1000-8000-00805f9b34fb
 */

const JK_SERVICE_UUID = 0xffe0;
const JK_CHAR_UUID = 0xffe1;

// Request header (bytes are reversed in response)
const REQ_HEADER = [0xaa, 0x55, 0x90, 0xeb];
const RES_HEADER = [0x55, 0xaa, 0xeb, 0x90];

// Commands
const CMD_CELL_DATA = 0x97;
const CMD_DEVICE_INFO = 0x96;

// Response frame types
const FRAME_SETTINGS = 0x01;
const FRAME_CELL_DATA = 0x02;
const FRAME_DEVICE_INFO = 0x03;

// Expected minimum response length for cell data
const MIN_CELL_DATA_LEN = 150;

export class JkBms extends EventTarget {
  constructor() {
    super();
    this._device = null;
    this._char = null;
    this._rxBuf = [];
    this._connected = false;
    this._pollTimer = null;
  }

  get connected() {
    return this._connected;
  }

  get deviceName() {
    return this._device?.name || "Unknown";
  }

  /** Request user to pick a BLE device and connect */
  async connect() {
    if (!navigator.bluetooth) {
      throw new Error("Web Bluetooth is not supported in this browser");
    }

    this._device = await navigator.bluetooth.requestDevice({
      filters: [{ services: [JK_SERVICE_UUID] }],
      optionalServices: [JK_SERVICE_UUID],
    });

    this._device.addEventListener(
      "gattserverdisconnected",
      () => this._onDisconnect()
    );

    const server = await this._device.gatt.connect();
    const service = await server.getPrimaryService(JK_SERVICE_UUID);
    this._char = await service.getCharacteristic(JK_CHAR_UUID);

    await this._char.startNotifications();
    this._char.addEventListener(
      "characteristicvaluechanged",
      (e) => this._onNotification(e)
    );

    this._connected = true;
    this.dispatchEvent(new Event("connected"));

    // Initial data request
    await this._requestCellData();
  }

  /** Disconnect from the BMS */
  disconnect() {
    this.stopPolling();
    if (this._device?.gatt?.connected) {
      this._device.gatt.disconnect();
    }
  }

  /** Start polling at the given interval (ms) */
  startPolling(intervalMs = 5000) {
    this.stopPolling();
    this._pollTimer = setInterval(() => this._requestCellData(), intervalMs);
  }

  /** Stop polling */
  stopPolling() {
    if (this._pollTimer) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
  }

  // --- Private ---

  _onDisconnect() {
    this._connected = false;
    this._char = null;
    this.stopPolling();
    this.dispatchEvent(new Event("disconnected"));
  }

  /** Build a 20-byte request frame */
  _buildFrame(cmd) {
    const frame = new Uint8Array(20);
    frame[0] = REQ_HEADER[0];
    frame[1] = REQ_HEADER[1];
    frame[2] = REQ_HEADER[2];
    frame[3] = REQ_HEADER[3];
    frame[4] = cmd;
    // Bytes 5-18 are zero (padding)
    let sum = 0;
    for (let i = 0; i < 19; i++) sum += frame[i];
    frame[19] = sum & 0xff;
    return frame;
  }

  async _requestCellData() {
    if (!this._char) return;
    try {
      this._rxBuf = [];
      await this._char.writeValueWithoutResponse(
        this._buildFrame(CMD_CELL_DATA)
      );
    } catch (err) {
      console.warn("BLE write failed:", err);
    }
  }

  async _requestDeviceInfo() {
    if (!this._char) return;
    try {
      this._rxBuf = [];
      await this._char.writeValueWithoutResponse(
        this._buildFrame(CMD_DEVICE_INFO)
      );
    } catch (err) {
      console.warn("BLE write failed:", err);
    }
  }

  /** Assemble incoming BLE notification chunks into a complete frame */
  _onNotification(event) {
    const value = new Uint8Array(event.target.value.buffer);

    // Detect start of a new frame
    if (
      value.length >= 4 &&
      value[0] === RES_HEADER[0] &&
      value[1] === RES_HEADER[1] &&
      value[2] === RES_HEADER[2] &&
      value[3] === RES_HEADER[3]
    ) {
      this._rxBuf = Array.from(value);
    } else {
      this._rxBuf.push(...value);
    }

    // Try to parse when we have enough data
    if (this._rxBuf.length >= MIN_CELL_DATA_LEN) {
      this._tryParse();
    }
  }

  _tryParse() {
    const buf = new Uint8Array(this._rxBuf);
    if (buf.length < 6) return;

    const frameType = buf[4];

    if (frameType === FRAME_CELL_DATA) {
      const data = this._parseCellData(buf);
      if (data) {
        this.dispatchEvent(
          new CustomEvent("data", { detail: data })
        );
      }
    } else if (frameType === FRAME_DEVICE_INFO) {
      const info = this._parseDeviceInfo(buf);
      if (info) {
        this.dispatchEvent(
          new CustomEvent("deviceinfo", { detail: info })
        );
      }
    }
  }

  /** Read a little-endian uint16 */
  _u16(buf, offset) {
    return buf[offset] | (buf[offset + 1] << 8);
  }

  /** Read a little-endian uint32 */
  _u32(buf, offset) {
    return (
      buf[offset] |
      (buf[offset + 1] << 8) |
      (buf[offset + 2] << 16) |
      ((buf[offset + 3] << 24) >>> 0)
    );
  }

  /** Read a little-endian int32 (signed) */
  _i32(buf, offset) {
    const val = this._u32(buf, offset);
    return val > 0x7fffffff ? val - 0x100000000 : val;
  }

  /** Convert raw temperature value to Celsius */
  _tempC(raw) {
    // JK-BMS uses offset encoding: value is temp + 100 (to avoid negatives)
    // Some firmware uses Kelvin × 10 (subtract 2731, divide by 10)
    // We detect which by checking if value > 1000 (likely deciKelvin)
    if (raw === 0) return null;
    if (raw > 1000) {
      return (raw - 2731) / 10;
    }
    return raw - 100;
  }

  /**
   * Parse cell data frame (type 0x02).
   *
   * Layout (byte offsets from frame start):
   *   0-4:   Header (55 AA EB 90 02)
   *   5:     Frame counter
   *   6-69:  Cell voltages, 32 × 2 bytes LE (mV), zero = unused
   *   70-71: MOS temperature (raw)
   *   72-73: Battery temperature sensor 1 (raw)
   *   74-75: Battery temperature sensor 2 (raw)
   *   76-79: Pack voltage, 4 bytes LE (mV)
   *   80-83: Pack current, 4 bytes LE signed (mA, positive = charge)
   *   84:    SoC (0-100%)
   *   85:    Number of temperature sensors
   *   86-89: Cycle count, 4 bytes LE
   *   90-93: Total cycle capacity (mAh), 4 bytes LE
   *   94-95: Number of battery strings
   *   96-97: Warning/alarm bits
   *   98-99: Status bits
   *  134-137: Uptime (seconds), 4 bytes LE
   *  138:    Charge MOSFET (0/1)
   *  139:    Discharge MOSFET (0/1)
   *  140:    Balancer active (0/1)
   */
  _parseCellData(buf) {
    if (buf.length < MIN_CELL_DATA_LEN) return null;

    // Cell voltages (mV)
    const cells = [];
    let minCell = Infinity,
      maxCell = -Infinity;
    for (let i = 0; i < 32; i++) {
      const mv = this._u16(buf, 6 + i * 2);
      if (mv > 0 && mv < 5000) {
        cells.push(mv);
        if (mv < minCell) minCell = mv;
        if (mv > maxCell) maxCell = mv;
      }
    }

    if (cells.length === 0) return null;

    const avgCell = Math.round(
      cells.reduce((a, b) => a + b, 0) / cells.length
    );

    // Temperatures
    const mosTemp = this._tempC(this._u16(buf, 70));
    const temp1 = this._tempC(this._u16(buf, 72));
    const temp2 = this._tempC(this._u16(buf, 74));

    // Pack totals
    const voltageMv = this._u32(buf, 76);
    const currentMa = this._i32(buf, 80);
    const soc = buf[84];
    const numTempSensors = buf[85];
    const cycles = this._u32(buf, 86);
    const totalCapMah = this._u32(buf, 90);
    const warnings = this._u16(buf, 96);
    const status = this._u16(buf, 98);

    // MOSFET and balancer status (check bounds)
    const chargeMos = buf.length > 138 ? buf[138] : null;
    const dischargeMos = buf.length > 139 ? buf[139] : null;
    const balancerActive = buf.length > 140 ? buf[140] : null;
    const uptimeS = buf.length > 137 ? this._u32(buf, 134) : null;

    const voltageV = voltageMv / 1000;
    const currentA = currentMa / 1000;
    const powerW = voltageV * currentA;

    return {
      cells, // array of mV values
      cellCount: cells.length,
      avgCellMv: avgCell,
      minCellMv: minCell === Infinity ? 0 : minCell,
      maxCellMv: maxCell === -Infinity ? 0 : maxCell,
      deltaCellMv: maxCell - minCell,
      voltageV,
      currentA,
      powerW,
      soc,
      mosTemp,
      temp1,
      temp2,
      numTempSensors,
      cycles,
      totalCapacityAh: totalCapMah / 1000,
      warnings,
      status,
      chargeMos: chargeMos === 1,
      dischargeMos: dischargeMos === 1,
      balancerActive: balancerActive === 1,
      uptimeS,
      timestamp: Date.now(),
    };
  }

  /** Parse device info frame (type 0x03) */
  _parseDeviceInfo(buf) {
    if (buf.length < 24) return null;

    // Device info is typically ASCII strings at known offsets
    // Extract what we can as text
    const decoder = new TextDecoder("utf-8");
    const raw = decoder.decode(buf.slice(6, Math.min(buf.length, 80)));
    // Clean non-printable characters
    const cleaned = raw.replace(/[^\x20-\x7E]/g, " ").trim();

    return { raw: cleaned };
  }
}
