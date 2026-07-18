# -*- coding: utf-8 -*-

import adsk, os
import re
from xml.etree.ElementTree import Element, SubElement
from . import Link, Joint
from ..utils import utils

def clean_name(name):
    """Replace spaces and special characters with underscores"""
    return re.sub('[ :()]', '_', name)

def write_link_urdf(joints_dict, repo, links_xyz_dict, file_name, inertial_dict, material_dict=None):
    """
    Write links information into urdf "repo/file_name"
    
    
    Parameters
    ----------
    joints_dict: dict
        information of the each joint
    repo: str
        the name of the repository to save the xml file
    links_xyz_dict: vacant dict
        xyz information of the each link
    file_name: str
        urdf full path
    inertial_dict:
        information of the each inertial
    material_dict:
        dictionary of material names for each link
    """
    if material_dict is None:
        material_dict = {}
    
    with open(file_name, mode='a') as f:
        # for base_link
        center_of_mass = inertial_dict['base_link']['center_of_mass']
        material = material_dict.get('base_link', 'silver')
        link = Link.Link(name='base_link', xyz=[0,0,0], 
            center_of_mass=center_of_mass, repo=repo,
            mass=inertial_dict['base_link']['mass'],
            inertia_tensor=inertial_dict['base_link']['inertia'],
            material=material)
        links_xyz_dict[link.name] = link.xyz
        link.make_link_xml()
        f.write(link.link_xml)
        f.write('\n')

        # others
        for joint in joints_dict:
            name = joints_dict[joint]['child']
            center_of_mass = \
                [ i-j for i, j in zip(inertial_dict[name]['center_of_mass'], joints_dict[joint]['xyz'])]
            material = material_dict.get(name, 'silver')
            link = Link.Link(name=name, xyz=joints_dict[joint]['xyz'],\
                center_of_mass=center_of_mass,\
                repo=repo, mass=inertial_dict[name]['mass'],\
                inertia_tensor=inertial_dict[name]['inertia'],
                material=material)
            links_xyz_dict[link.name] = link.xyz            
            link.make_link_xml()
            f.write(link.link_xml)
            f.write('\n')


def write_joint_urdf(joints_dict, repo, links_xyz_dict, file_name):
    """
    Write joints and transmission information into urdf "repo/file_name"
    
    
    Parameters
    ----------
    joints_dict: dict
        information of the each joint
    repo: str
        the name of the repository to save the xml file
    links_xyz_dict: dict
        xyz information of the each link
    file_name: str
        urdf full path
    """
    
    with open(file_name, mode='a') as f:
        for j in joints_dict:
            # Clean the joint name to remove spaces
            clean_joint_name = clean_name(j)
            
            parent = joints_dict[j]['parent']
            child = joints_dict[j]['child']
            joint_type = joints_dict[j]['type']
            upper_limit = joints_dict[j]['upper_limit']
            lower_limit = joints_dict[j]['lower_limit']
            try:
                xyz = [round(p-c, 6) for p, c in \
                    zip(links_xyz_dict[parent], links_xyz_dict[child])]  # xyz = parent - child
            except KeyError as ke:
                app = adsk.core.Application.get()
                ui = app.userInterface
                ui.messageBox("There seems to be an error with the connection between\n\n%s\nand\n%s\n\nCheck \
whether the connections\nparent=component2=%s\nchild=component1=%s\nare correct or if you need \
to swap component1<=>component2"
                % (parent, child, parent, child), "Error!")
                quit()
                
            joint = Joint.Joint(name=clean_joint_name, joint_type = joint_type, xyz=xyz, \
            axis=joints_dict[j]['axis'], parent=parent, child=child, \
            upper_limit=upper_limit, lower_limit=lower_limit)
            joint.make_joint_xml()
            joint.make_transmission_xml()
            f.write(joint.joint_xml)
            f.write('\n')

def write_gazebo_endtag(file_name):
    """
    Write about gazebo_plugin and the </robot> tag at the end of the urdf
    
    
    Parameters
    ----------
    file_name: str
        urdf full path
    """
    with open(file_name, mode='a') as f:
        f.write('</robot>\n')
        

def write_urdf(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, save_dir, material_dict=None):
    try: os.mkdir(save_dir + '/urdf')
    except: pass 

    file_name = save_dir + '/urdf/' + robot_name + '.xacro'  # the name of urdf file
    repo = package_name + '/meshes/'  # the repository of binary stl files
    with open(file_name, mode='w') as f:
        f.write('<?xml version="1.0" ?>\n')
        f.write('<robot name="{}" xmlns:xacro="http://www.ros.org/wiki/xacro">\n'.format(robot_name))
        f.write('\n')
        f.write('<xacro:include filename="$(find {})/urdf/materials.xacro" />'.format(package_name))
        f.write('\n')
        f.write('<xacro:include filename="$(find {})/urdf/{}.trans" />'.format(package_name, robot_name))
        f.write('\n')
        f.write('<xacro:include filename="$(find {})/urdf/{}.gazebo" />'.format(package_name, robot_name))
        f.write('\n')

    write_link_urdf(joints_dict, repo, links_xyz_dict, file_name, inertial_dict, material_dict)
    write_joint_urdf(joints_dict, repo, links_xyz_dict, file_name)
    write_gazebo_endtag(file_name)

def write_materials_xacro(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, save_dir, color_dict=None):
    """
    Write materials.xacro with colors extracted from Fusion
    
    Parameters
    ----------
    color_dict: dict
        Dictionary mapping material names to RGBA strings
    """
    try: os.mkdir(save_dir + '/urdf')
    except: pass  

    if color_dict is None:
        color_dict = {'silver': '0.700 0.700 0.700 1.000'}

    file_name = save_dir + '/urdf/materials.xacro'  # the name of urdf file
    with open(file_name, mode='w') as f:
        f.write('<?xml version="1.0" ?>\n')
        f.write('<robot name="{}" xmlns:xacro="http://www.ros.org/wiki/xacro" >\n'.format(robot_name))
        f.write('\n')
        
        # Write all materials from color_dict
        for material_name, color_rgba in color_dict.items():
            f.write('<material name="{}">\n'.format(material_name))
            f.write('  <color rgba="{}"/>\n'.format(color_rgba))
            f.write('</material>\n')
            f.write('\n')
        
        f.write('</robot>\n')

def write_transmissions_xacro(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, save_dir):
    """
    Write joints and transmission information into urdf "repo/file_name"
    
    
    Parameters
    ----------
    joints_dict: dict
        information of the each joint
    repo: str
        the name of the repository to save the xml file
    links_xyz_dict: dict
        xyz information of the each link
    file_name: str
        urdf full path
    """
    
    file_name = save_dir + '/urdf/{}.trans'.format(robot_name)  # the name of urdf file
    with open(file_name, mode='w') as f:
        f.write('<?xml version="1.0" ?>\n')
        f.write('<robot name="{}" xmlns:xacro="http://www.ros.org/wiki/xacro" >\n'.format(robot_name))
        f.write('\n')

        for j in joints_dict:
            # Clean the joint name to remove spaces
            clean_joint_name = clean_name(j)
            
            parent = joints_dict[j]['parent']
            child = joints_dict[j]['child']
            joint_type = joints_dict[j]['type']
            upper_limit = joints_dict[j]['upper_limit']
            lower_limit = joints_dict[j]['lower_limit']
            try:
                xyz = [round(p-c, 6) for p, c in \
                    zip(links_xyz_dict[parent], links_xyz_dict[child])]  # xyz = parent - child
            except KeyError as ke:
                app = adsk.core.Application.get()
                ui = app.userInterface
                ui.messageBox("There seems to be an error with the connection between\n\n%s\nand\n%s\n\nCheck \
whether the connections\nparent=component2=%s\nchild=component1=%s\nare correct or if you need \
to swap component1<=>component2"
                % (parent, child, parent, child), "Error!")
                quit()
                
            joint = Joint.Joint(name=clean_joint_name, joint_type = joint_type, xyz=xyz, \
            axis=joints_dict[j]['axis'], parent=parent, child=child, \
            upper_limit=upper_limit, lower_limit=lower_limit)
            if joint_type != 'fixed':
                joint.make_transmission_xml()
                f.write(joint.tran_xml)
                f.write('\n')

        f.write('</robot>\n')

def write_gazebo_xacro(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, save_dir, material_dict=None):
    try: os.mkdir(save_dir + '/urdf')
    except: pass  

    if material_dict is None:
        material_dict = {}

    file_name = save_dir + '/urdf/' + robot_name + '.gazebo'  # the name of urdf file
    repo = robot_name + '/meshes/'  # the repository of binary stl files
    with open(file_name, mode='w') as f:
        f.write('<?xml version="1.0" ?>\n')
        f.write('<robot name="{}" xmlns:xacro="http://www.ros.org/wiki/xacro" >\n'.format(robot_name))
        f.write('\n')

        # Create gazebo plugin with robot namespace
        gazebo = Element('gazebo')
        plugin = SubElement(gazebo, 'plugin')
        plugin.attrib = {'name':'gazebo_ros_control', 'filename':'libgazebo_ros_control.so'}
        
        # Add robot namespace
        robot_namespace = SubElement(plugin, 'robotNamespace')
        robot_namespace.text = '/' + robot_name
        
        control_period = SubElement(plugin, 'controlPeriod')
        control_period.text = '0.001'
        
        gazebo_xml = "\n".join(utils.prettify(gazebo).split("\n")[1:])
        f.write(gazebo_xml)

        # for base_link
        material_name = material_dict.get('base_link', 'silver')
        f.write('<gazebo reference="base_link">\n')
        f.write('  <material>Gazebo/{}</material>\n'.format(material_name))
        f.write('  <mu1>0.2</mu1>\n')
        f.write('  <mu2>0.2</mu2>\n')
        f.write('  <selfCollide>true</selfCollide>\n')
        f.write('  <gravity>true</gravity>\n')
        f.write('</gazebo>\n')
        f.write('\n')

        # others
        for joint in joints_dict:
            name = joints_dict[joint]['child']
            material_name = material_dict.get(name, 'silver')
            f.write('<gazebo reference="{}">\n'.format(name))
            f.write('  <material>Gazebo/{}</material>\n'.format(material_name))
            f.write('  <mu1>0.2</mu1>\n')
            f.write('  <mu2>0.2</mu2>\n')
            f.write('  <selfCollide>true</selfCollide>\n')
            f.write('</gazebo>\n')
            f.write('\n')

        f.write('</robot>\n')

def write_display_launch(package_name, robot_name, save_dir):
    """
    write display launch file "save_dir/launch/display.launch"
    
    Parameter
    ---------
    package_name: str
        name of the package
    robot_name: str
        name of the robot
    save_dir: str
        path of the repository to save
    """   
    try: os.mkdir(save_dir + '/launch')
    except: pass     
    
    file_name = save_dir + '/launch/display.launch'    
    with open(file_name, mode='w') as f:
        f.write('<?xml version="1.0"?>\n')
        f.write('<launch>\n')
        f.write('  <arg name="model" default="$(find {})/urdf/{}.xacro"/>\n'.format(package_name, robot_name))
        f.write('  <arg name="gui" default="true"/>\n')
        f.write('  <arg name="rvizconfig" default="$(find {})/launch/urdf.rviz"/>\n'.format(package_name))
        f.write('  \n')
        f.write('  <param name="robot_description" command="$(find xacro)/xacro $(arg model)"/>\n')
        f.write('  <param name="use_gui" value="$(arg gui)"/>\n')
        f.write('  \n')
        f.write('  <node if="$(arg gui)" name="joint_state_publisher_gui" pkg="joint_state_publisher_gui" type="joint_state_publisher_gui">\n')
        f.write('    <param name="rate" value="144.0"/>\n')
        f.write('    <param name="publish_rate" value="144.0"/>\n')
        f.write('  </node>\n')
        f.write('  \n')
        f.write('  <node unless="$(arg gui)" name="joint_state_publisher" pkg="joint_state_publisher" type="joint_state_publisher">\n')
        f.write('    <param name="rate" value="144.0"/>\n')
        f.write('    <param name="publish_rate" value="144.0"/>\n')
        f.write('  </node>\n')
        f.write('  \n')
        f.write('  <node name="robot_state_publisher" pkg="robot_state_publisher" type="robot_state_publisher">\n')
        f.write('    <param name="publish_frequency" value="144.0"/>\n')
        f.write('  </node>\n')
        f.write('  \n')
        f.write('  <node name="rviz" pkg="rviz" type="rviz" args="-d $(arg rvizconfig)" required="true"/>\n')
        f.write('</launch>\n')


def write_gazebo_launch(package_name, robot_name, save_dir):
    """
    write gazebo launch file "save_dir/launch/gazebo.launch"
    
    Parameter
    ---------
    package_name: str
        name of the package
    robot_name: str
        name of the robot
    save_dir: str
        path of the repository to save
    """
    
    try: os.mkdir(save_dir + '/launch')
    except: pass     
    
    file_name = save_dir + '/launch/gazebo.launch'    
    with open(file_name, mode='w') as f:
        f.write('<launch>\n')
        f.write('  \n')
        f.write('  <param name="robot_description" command="$(find xacro)/xacro $(find {})/urdf/{}.xacro"/>\n'.format(package_name, robot_name))
        f.write('  \n')
        f.write('  \n')
        f.write('  <include file="$(find gazebo_ros)/launch/empty_world.launch">\n')
        f.write('    <arg name="paused" value="true"/>\n')
        f.write('    <arg name="use_sim_time" value="true"/>\n')
        f.write('    <arg name="gui" value="true"/>\n')
        f.write('    <arg name="headless" value="false"/>\n')
        f.write('    <arg name="debug" value="false"/>\n')
        f.write('  </include>\n')
        f.write('  \n')
        f.write('  \n')
        f.write('  <node name="spawn_urdf" pkg="gazebo_ros" type="spawn_model" \n')
        f.write('        args="-param robot_description -urdf -model {} -x 0 -y 0 -z 0.5" \n'.format(robot_name))
        f.write('        respawn="false" output="screen"/>\n')
        f.write('</launch>\n')


def write_control_launch(package_name, robot_name, save_dir, joints_dict):
    """
    write control launch file "save_dir/launch/controller.launch"
    
    
    Parameter
    ---------
    package_name: str
        name of the package
    robot_name: str
        name of the robot
    save_dir: str
        path of the repository to save
    joints_dict: dict
        information of the joints
    """
    try: os.mkdir(save_dir + '/launch')
    except: pass     
    
    file_name = save_dir + '/launch/controller.launch'    
    with open(file_name, mode='w') as f:
        f.write('<launch>\n')
        f.write('  <rosparam file="$(find {})/launch/controller.yaml" command="load"/>\n'.format(package_name))
        f.write('  <node name="controller_spawner" pkg="controller_manager" type="spawner" respawn="false" output="screen" ns="{}" \n'.format(robot_name))
        f.write('        args="')
        
        # Write each joint controller
        controller_list = []
        for j in joints_dict:
            joint_type = joints_dict[j]['type']
            if joint_type != 'fixed':
                clean_joint_name = clean_name(j)
                controller_list.append(clean_joint_name + '_position_controller')
        
        controller_list.append('joint_state_controller')
        f.write(' '.join(controller_list))
        f.write('"/>\n')
        f.write('  <node name="robot_state_publisher" pkg="robot_state_publisher" type="robot_state_publisher" respawn="false" output="screen">\n')
        f.write('    <remap from="/joint_states" to="/{}/joint_states"/>\n'.format(robot_name))
        f.write('  </node>\n')
        f.write('</launch>\n')
        

def write_yaml(package_name, robot_name, save_dir, joints_dict):
    """
    write yaml file "save_dir/launch/controller.yaml"
    
    
    Parameter
    ---------
    package_name: str
        name of the package
    robot_name: str
        name of the robot
    save_dir: str
        path of the repository to save
    joints_dict: dict
        information of the joints
    """
    try: os.mkdir(save_dir + '/launch')
    except: pass 

    controller_name = robot_name + '_controller'
    file_name = save_dir + '/launch/controller.yaml'
    with open(file_name, 'w') as f:
        f.write(controller_name + ':\n')
        # joint_state_controller
        f.write('  # Publish all joint states -----------------------------------\n')
        f.write('  joint_state_controller:\n')
        f.write('    type: joint_state_controller/JointStateController\n')  
        f.write('    publish_rate: 50\n\n')
        # position_controllers
        f.write('  # Position Controllers --------------------------------------\n')
        for joint in joints_dict:
            joint_type = joints_dict[joint]['type']
            if joint_type != 'fixed':
                clean_joint_name = clean_name(joint)
                f.write('  {}_position_controller:\n'.format(clean_joint_name))
                f.write('    type: effort_controllers/JointPositionController\n')
                f.write('    joint: {}\n'.format(clean_joint_name))
                f.write('    pid: {p: 100.0, i: 0.01, d: 10.0}\n')