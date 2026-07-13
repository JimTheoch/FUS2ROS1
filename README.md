# FUS2ROS1 - Fusion 360 to ROS1 Exporter

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![ROS1](https://img.shields.io/badge/ROS-Noetic-brightgreen)](http://wiki.ros.org/noetic)
[![Python](https://img.shields.io/badge/Python-3.6+-blue.svg)](https://www.python.org/downloads/)
[![Fusion 360](https://img.shields.io/badge/Fusion%20360-API-orange)](https://help.autodesk.com/view/fusion360/ENU/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)
> **Fork Notice:** This project is a fork of [syuntoku14/fusion2urdf](https://github.com/syuntoku14/fusion2urdf). Special thanks to **Syuntoku14** for the original work and inspiration!


A Fusion 360 Python script that automatically generates a complete ROS1 package with:
- URDF/Xacro robot description
- STL mesh files
- Gazebo simulation files
- ROS controllers configuration
- Launch files

## Features
- 🔄 Automatic joint detection and conversion (revolute, prismatic, continuous, fixed)
- 📐 Physical properties extraction (mass, inertia, center of mass)
- 🎨 Mesh Quality Selection - Choose from Low, Medium, or High quality STL exports
- 🚀 ROS Control setup (position controllers)
- 🤖 Gazebo simulation ready
- 🧹 Automatic name sanitization (spaces → underscores)
- 📁 Complete ROS package structure generation
- ✅ No need for grounding/un-grounding parametric or direct modeling

## ⚠️ Limitations & Known Issues

### Assembly Structure Limitations

- **No Nested Assemblies Support**: The exporter only works with flat assembly structures. Sub-assemblies (nested components) are not supported and will cause errors.
  
- **No In-Place Components**: Components created using "Create In-Place" feature may not export correctly. Use external components instead.

- **No Patterned Components**: Components created with patterns (rectangular, circular, or mirror) may not be properly recognized.

- **No Derived Components**: Components derived from other designs may cause issues with the export process.

### Mesh Export Limitations

- **Three Quality Levels**: Fusion 360 API only supports Low, Medium, and High mesh refinement. "Very High" is not available.

| Quality | File Size | Export Time | Detail Level | Best For |
|---------|-----------|-------------|--------------|----------|
| **Low** | Smallest | Fastest | Basic shape | **Default**, simple geometries |
| **Medium** | Medium | Moderate | Balanced | Most use cases |
| **High** | Largest | Slower | Fine details | Detailed visualizations |

- **Binary STL Format**: All meshes are exported as binary STL files for smaller file sizes.

- **Large Assemblies**: Exporting very large assemblies with many components may take several minutes.

### Joint Type Limitations

| Supported | Not Supported (or Partial) |
|-----------|---------------------------|
| ✅ Revolute | ❌ Cylindrical |
| ✅ Prismatic | ❌ PinSlot |
| ✅ Continuous | ❌ Planner |
| ✅ Fixed | ❌ Ball |
| | ❌ Screw |

### Joint Limits Requirements

- **Revolute joints**: Both upper and lower limits MUST be set. If only one limit is set or neither is set, the joint will be converted to `continuous` type.
  
- **Prismatic joints**: Both upper and lower limits MUST be set. If only one limit is set or neither is set, the export will fail with an error message.

## Installation

1. Copy the script to your Fusion 360 Scripts directory:
   - Windows: `%APPDATA%/Autodesk/Autodesk Fusion 360/API/Scripts/`
   - Mac: `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/Scripts/`

2. In Fusion 360, go to **Utilities/Tools → Add-Ins → Scripts and Add-Ins**
3. Find the script and click **Run**

## Usage

1. Open your assembly in Fusion 360
2. Run the FUS2ROS1 script
3. Select the **Base Link Component** from the dropdown
4. Choose an **Export Folder** (your ROS workspace path)
5. Click **Generate Package**

## 📂 Output Structure
```
your_robot_description/
├── urdf/
│ ├── your_robot.xacro # Main URDF
│ ├── materials.xacro # Material definitions
│ ├── your_robot.trans # Transmission configurations
│ └── your_robot.gazebo # Gazebo settings
├── meshes/
│ └── *.stl # 3D mesh files
├── launch/
│ ├── display.launch # RViz visualization
│ ├── gazebo.launch # Gazebo simulation
│ ├── controller.launch # ROS controllers
│ └── controller.yaml # PID controller configuration 
├── CMakeLists.txt
└── package.xml
```

## 🎮 Launch Your Robot

### Visualize in RViz
```bash
roslaunch your_robot_description display.launch
```

### Simulate in Gazebo
```bash
roslaunch your_robot_description gazebo.launch
```

## 🔧 Controller Configuration

The exporter automatically creates PID controllers for each non-fixed joint:

```yaml
your_robot_controller:
  joint_state_controller:
    type: joint_state_controller/JointStateController
    publish_rate: 50

  joint1_position_controller:
    type: effort_controllers/JointPositionController
    joint: joint1
    pid: {p: 100.0, i: 0.01, d: 10.0}
```

## 🙏 Acknowledgments
Syuntoku14 - Original fusion2urdf project that made this possible

Masaki Yamamoto - For the coordinate transformation solution

Autodesk - For Fusion 360 and its Python API

Open Robotics - For ROS and Gazebo

All contributors and users of the original fusion2urdf
