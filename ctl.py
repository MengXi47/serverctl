import subprocess
import time
import sys
import os
import re

# ==============================================================================
# 🛠️ 使用者設定區
# ==============================================================================
IDRAC_IP = "192.168.0.150"
IDRAC_USER = "root"
IDRAC_PASS = "calvin"
# ==============================================================================


class DellServer:
    def __init__(self, ip, user, password):
        self.ip = ip
        self.user = user
        self.password = password
        self.base_cmd = [
            "ipmitool",
            "-I",
            "lanplus",
            "-H",
            self.ip,
            "-U",
            self.user,
            "-P",
            self.password,
        ]

    def run(self, args, capture=True):
        try:
            result = subprocess.run(
                self.base_cmd + args,
                check=True,
                capture_output=capture,
                text=True,
                timeout=12,
            )
            return result.stdout.strip() if capture else True
        except:
            return None

    def get_sensors(self):
        data = {
            "pwr_watts": "N/A",
            "cpu_temp": [],
            "inlet_temp": "N/A",
            "fans": [],
        }

        # 1. 功耗抓取
        pwr_raw = self.run(["dcmi", "power", "reading"])
        if pwr_raw:
            match = re.search(
                r"Instantaneous power reading:\s+(\d+)\s+Watts", pwr_raw
            )
            if match:
                data["pwr_watts"] = f"{match.group(1)} Watts"

        # 2. 溫度與風扇抓取 (elist full)
        sdr_raw = self.run(["sdr", "elist", "full"])
        if sdr_raw:
            for line in sdr_raw.split("\n"):
                if not line or "|" not in line:
                    continue
                low_line = line.lower()
                parts = line.split("|")
                sensor_name = parts[0].strip()
                sensor_value = parts[-1].strip()

                if "inlet temp" in low_line:
                    data["inlet_temp"] = sensor_value
                elif "temp" in low_line and "degrees c" in low_line:
                    if "inlet" not in low_line:
                        data["cpu_temp"].append(
                            f"{sensor_name}: {sensor_value}"
                        )
                elif "fan" in low_line and "rpm" in low_line:
                    data["fans"].append(f"{sensor_name}: {sensor_value}")

        return data

    def set_fan_manual(self, percent):
        hex_spd = hex(percent)
        self.run(["raw", "0x30", "0x30", "0x01", "0x00"], capture=False)
        self.run(
            ["raw", "0x30", "0x30", "0x02", "0xff", hex_spd], capture=False
        )

    def set_fan_auto(self):
        self.run(["raw", "0x30", "0x30", "0x01", "0x01"], capture=False)

    def power_control(self, action):
        return self.run(["chassis", "power", action], capture=False)


# ==============================================================================
# UI 介面與顯示
# ==============================================================================


def show_dashboard(server):
    os.system("cls" if os.name == "nt" else "clear")
    print("═" * 60)
    print(f"🖥️  R730xd 控制中心 | IP: {server.ip}")
    print(f"⏰ 最後更新: {time.strftime('%H:%M:%S')}")
    print("═" * 60)

    p_status = server.run(["chassis", "power", "status"]) or "Unknown"
    p_color = "🟢" if "on" in p_status.lower() else "🔴"
    print(f"[{p_color} 電源狀態]: {p_status.upper()}")

    if "on" in p_status.lower():
        print("⏳ 正在讀取感測器數據...")
        sensors = server.get_sensors()

        # 覆蓋剛剛的「正在讀取」文字
        print(f"⚡ [即時功耗]: {sensors['pwr_watts']}")
        print(f"🌡️  [進氣溫度]: {sensors['inlet_temp']}")

        print("\n🔥 [核心溫度]:")
        if not sensors["cpu_temp"]:
            print("   (無法讀取數值)")
        for t in sensors["cpu_temp"]:
            print(f"   └─ {t}")

        print("\n🌀 [風扇轉速]:")
        if not sensors["fans"]:
            print("   (無法讀取數值)")
        for f in sensors["fans"]:
            print(f"   └─ {f}")

    print("\n" + "═" * 60)
    print(" 1. 手動轉速% | 2. 自動溫控 | 3. 電源控制")
    print(" 4. 重新整理  | 0. 退出控制中心 (Q)")
    print("═" * 60)


def main():
    server = DellServer(IDRAC_IP, IDRAC_USER, IDRAC_PASS)
    while True:
        show_dashboard(server)
        choice = input("\n👉 指令: ").strip().lower()

        if choice == "1":
            try:
                spd = int(input("   輸入 0-100: "))
                server.set_fan_manual(spd)
                print(f"   ✅ 已發送 {spd}% 指令")
                time.sleep(1)
            except:
                pass
        elif choice == "2":
            server.set_fan_auto()
            print("   ✅ 已切換為自動溫控")
            time.sleep(1)
        elif choice == "3":
            p = input("   a.開機 / b.軟關機 / c.強制重啟: ").lower()
            if p == "a":
                server.power_control("on")
            elif p == "b":
                server.power_control("soft")
            elif p == "c":
                server.power_control("reset")
            time.sleep(2)
        elif choice == "4" or choice == "":
            print("   🔄 正在重新整理...")
            continue  # 直接觸發迴圈開始的 show_dashboard
        elif choice == "0" or choice == "q":
            break
        else:
            print("   ⚠️ 無效指令，重新整理中...")
            time.sleep(0.5)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 已退出控制中心")
