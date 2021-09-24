import random
import open3d as o3d
#import time
import pybullet as p
import numpy as np
from numpy import linalg
from matplotlib import pyplot as plt
import sim_class
from PIL import Image
import concurrent.futures
import tool
import cv2
from scipy.spatial.transform import Rotation as R
import math
from math import sin, cos, pi

from collections import Counter
import concurrent.futures
from sys import argv
import gc

def Frame(pos, ori):
    mat = R.from_quat(ori).as_matrix()
    F = np.concatenate(
        [np.concatenate([mat, [[0, 0, 0]]], axis=0), np.reshape([*pos, 1.], [-1, 1])], axis=1
    )
    return F

def find_center(mask):
    g = np.mgrid[0:(mask.shape[0]),0:(mask.shape[1])]
    multiple_ = np.stack([mask,mask],0)*g
    total_sum = np.sum(multiple_,axis = (1,2))
    total_number = np.sum(mask)
    average = total_sum/total_number
    return average.astype(int)


loop_id = argv[1]
img_save_dir = './pre_data'+str(loop_id)+'/train/input/'
label_save_dir = './pre_data'+str(loop_id)+'/train/label/'
state_save_dir = './pre_data'+str(loop_id)+'/train/state/'
seg_map_dir = './pre_data'+str(loop_id)+'/train/seg_save/'
sec_input_dir = './pre_data'+str(loop_id)+'/train/sec_input/'

tool.create_dir_not_exist(img_save_dir)
tool.create_dir_not_exist(label_save_dir)
tool.create_dir_not_exist(state_save_dir)
tool.create_dir_not_exist(seg_map_dir)
tool.create_dir_not_exist(sec_input_dir)

image_pixel_before = 320
image_pixel_after = 240

example_number_need_collect = 200

def custom_method_saveimg(floder_id):

    #floder_id = 0
    debug_display = 0

    object_ran = 1#random.randint(0,2)
    num_obj = 140+random.randint(-10,10)
    num_rotation = 6
    #    object_ran = 0
    if object_ran == 0:
        object_path = './objurdf/duomi/duomi.urdf'
        obj_shape = 'domino'
    elif object_ran == 1:
        object_path = './objurdf/cy/cy.urdf'
        obj_shape = 'go_stone'
    #        num_obj = 130+random.randint(-10,10)
    elif object_ran == 2:
        object_path = './objurdf/sj/sj.urdf'
        obj_shape = 'key'

    ap_ws = [0, 1, 2, 3]
    p_ws = [0,10,20]
    r_ws = [0,-10,10]
    fl_ws = [0,1,2,3]

    GUI = False
    EyePosition=[0,0,0.46+random.uniform(-0.01,0.01)]
    TargetPosition=[0,0,0]
    fov_d = 69.25+random.uniform(-0.25,0.25)
    near = 0.001
    far = EyePosition[2]+0.05
    state_save_path = state_save_dir+str(floder_id)+'.bullet'
    robotStartOrn = p.getQuaternionFromEuler([0, 0, 0])

    sim = sim_class.Sim(state_save_path, num_obj, GUI, image_pixel_before, EyePosition,TargetPosition,fov_d,far,near,robotStartOrn,object_path)
    #build env_sim
    sim.build_e()
    #渲染图像
    rgbImg, depthImg, segImg = sim.render()
    img_d, float_depth, poke_pos_map = sim.after_render()
    img_d[np.where(segImg==0)] = 255

    #depthImg = np.floor(depthImg*255/EyePosition[2]).astype(np.uint8)
    #depthImg = depthImg[:,:,np.newaxis]
    #depthImg = np.concatenate((depthImg, depthImg, depthImg), axis=2)
    label_long = np.ones((image_pixel_after,image_pixel_after,num_rotation))*255
    mask_accept_thed = 500
    #count_mask = 1
    segImg_copy = segImg.copy()
    segImg_copy[np.where(segImg_copy<2)] = 0
    counter_dict = Counter(segImg_copy[np.where(segImg_copy>0)])
    counter_dict = {k : v for k, v in counter_dict.items() if v > mask_accept_thed}
    #print(len(list(counter_dict.keys())))
    for i in list(counter_dict.keys()):
        #for i in range(2,num_obj+2):
        mask_ind = np.where(segImg==i)
        mask = np.zeros((image_pixel_after,image_pixel_after))
        mask[mask_ind] = 1
        #print('test sum mask', np.sum(mask))
        if np.sum(mask) >= mask_accept_thed:
            #print('check mask num', count_mask)
            #count_mask = count_mask + 1
            mask = mask.astype(np.uint8)
            obj_pos, obj_ori = p.getBasePositionAndOrientation(i)


            if obj_shape == 'cy':
                obj_z_in_w = Frame(obj_pos, obj_ori) @ np.array([0, 0, 1, 1])
                abs_yaw = math.acos(np.dot(obj_z_in_w[:2]/linalg.norm(obj_z_in_w[:2]),np.array([0,1])))
                if np.dot(obj_z_in_w[:2],np.array([1,0])) > 0:
                    yaw_long = abs_yaw
                else:
                    yaw_long = math.radians(360) - abs_yaw
                #print('gripper yaw', math.degrees(yaw_long))

                rot_ind_long = round(yaw_long/math.radians(60))
                if yaw_long > math.radians(330):
                    rot_ind_long = 0
                #print('test rot_ind_long', rot_ind_long)


                depth_copy = img_d.copy()
                d = 8
                [c_y,c_x] = find_center(mask)
                good_pt_x = int(c_x+(d)*cos(yaw_long-math.pi/2))
                good_pt_y = int(c_y+(d)*sin(yaw_long-math.pi/2))
                bad_pt_x = int(c_x-d*cos(yaw_long-math.pi/2))
                bad_pt_y = int(c_y-d*sin(yaw_long-math.pi/2))
                # Mesh grid for bad points
                bad_area_h = 2#35
                bad_area_w = 2#25
                good_area_h = 2
                good_area_w = 2#15
                bad_x, bad_y = np.meshgrid(np.arange(bad_area_h), np.arange(bad_area_w))
                bad_x = bad_x.flatten()
                bad_x = bad_x[:,np.newaxis]
                bad_y = bad_y.flatten()
                bad_y = bad_y[:,np.newaxis]
                bad_pts = np.concatenate((bad_x,bad_y),axis=1)
                rot_matrix = np.array([[cos(yaw_long-pi/2), -sin(yaw_long-pi/2)],
                                        [sin(yaw_long-pi/2), cos(yaw_long-pi/2)]])
                bad_pts = bad_pts @ rot_matrix
                shift = np.ones((bad_pts.shape[0],bad_pts.shape[1]))
                shift[:,0] = shift[:,0]*(bad_pt_y-bad_area_h*(cos(yaw_long-pi/2)+sin(yaw_long-pi/2))/2)
                shift[:,1] = shift[:,1]*(bad_pt_x-bad_area_h*(cos(yaw_long-pi/2)-sin(yaw_long-pi/2))/2)
                bad_pts = bad_pts + shift
                for bad_pts_ind in range(bad_pts.shape[0]):
                    if int(bad_pts[bad_pts_ind][0]>0) and int(bad_pts[bad_pts_ind][0]<image_pixel_after) and int(bad_pts[bad_pts_ind][1]>0) and int(bad_pts[bad_pts_ind][1]<image_pixel_after):
                        #if int(bad_pts[bad_pts_ind][0]%2) == 0:
                        #label[int(bad_pts[bad_pts_ind][0]),int(bad_pts[bad_pts_ind][1])] = 0
                        #label_rot[int(bad_pts[bad_pts_ind][0]),int(bad_pts[bad_pts_ind][1]),rot_ind_long] = 0
                        label_long[int(bad_pts[bad_pts_ind][0]),int(bad_pts[bad_pts_ind][1]),rot_ind_long] = 0
                        cv2.circle(depth_copy, (int(bad_pts[bad_pts_ind][1]), int(bad_pts[bad_pts_ind][0])), 1, (255, 0, 0), -1)

                good_x, good_y = np.meshgrid(np.arange(good_area_h), np.arange(good_area_w))
                good_x = good_x.flatten()
                good_x = good_x[:,np.newaxis]
                good_y = good_y.flatten()
                good_y = good_y[:,np.newaxis]
                good_pts = np.concatenate((good_x,good_y),axis=1)
                rot_matrix = np.array([[cos(yaw_long-pi/2), -sin(yaw_long-pi/2)],
                                        [sin(yaw_long-pi/2), cos(yaw_long-pi/2)]])
                good_pts = good_pts @ rot_matrix
                shift = np.ones((good_pts.shape[0],good_pts.shape[1]))
                shift[:,0] = shift[:,0]*(good_pt_y-good_area_h*(cos(yaw_long-pi/2)+sin(yaw_long-pi/2))/2)
                shift[:,1] = shift[:,1]*(good_pt_x-good_area_h*(cos(yaw_long-pi/2)-sin(yaw_long-pi/2))/2)
                good_pts = good_pts + shift
                for good_pts_ind in range(good_pts.shape[0]):
                    if int(good_pts[good_pts_ind][0]>0) and int(good_pts[good_pts_ind][0]<image_pixel_after) and int(good_pts[good_pts_ind][1]>0) and int(good_pts[good_pts_ind][1]<image_pixel_after):
                        label_long[int(good_pts[good_pts_ind][0]),int(good_pts[good_pts_ind][1]),rot_ind_long] = 128
                        cv2.circle(depth_copy, (int(good_pts[good_pts_ind][1]), int(good_pts[good_pts_ind][0])), 1, (255, 255, 0), -1)


                if debug_display == 1:
                    [_,contours,hierarchy] = cv2.findContours(mask,cv2.RETR_TREE,cv2.CHAIN_APPROX_NONE)
                    cnt = contours[0]
                    for j in range(len(contours)):
                        if(len(contours[j]) > len(cnt)):
                            cnt = contours[j]
                    hull = cv2.convexHull(cnt,returnPoints = True)
                    rect = cv2.minAreaRect(hull)
                    box = cv2.boxPoints(rect)
                    box = np.int0(box)
                    cv2.drawContours(depth_copy,[box],0,(0,0,0),1)
                    cv2.putText(depth_copy,str(math.degrees(yaw_long)), (50,50), cv2.FONT_HERSHEY_SIMPLEX, 1, 255)
                    #cv2.putText(depth_copy,str(math.degrees(yaw_short)), (100,100), cv2.FONT_HERSHEY_SIMPLEX, 2, 255)
                    cv2.circle(depth_copy,(good_pt_x, good_pt_y), 1, (0,255,0),-1)
                    cv2.circle(depth_copy,(bad_pt_x, bad_pt_y), 1, (0,0,255),-1)
                    #plt.figure(figsize=(20,10))
                    #plt.imshow(depth_copy[:,:,[2,1,0]])#[:,:,::-1])
                    #plt.show()
                    depth_save = Image.fromarray(depth_copy)
                    depth_save.save('./pre_data'+str(loop_id)+'/train/'+'floder_'+str(floder_id)+'_obj_'+str(i)+'_yaw_'+str(rot_ind_long)+'.png','PNG')

    for i in range(num_rotation):
        for pt in p_ws:
            for rt in r_ws:
                for ap_ind in ap_ws:
                    for fl_ind in fl_ws:
                        if fl_ind != 0 and np.min(label_long[:,:,i])<255:
                            img_d_rot_temp = Image.fromarray(img_d)
                            img_d_rot = img_d_rot_temp.rotate(i*60, fillcolor=(255,255,255))
                            img_d_rot_path = img_save_dir+'cy_'+'num_'+str(floder_id)+'_yaw_'+str(int(i*60)) \
                                                        +'_ap_'+str(int(ap_ind))+'_pitch_'+str(int(pt)) \
                                                        +'_roll_'+str(int(rt))+'_fl_'+str(int(fl_ind))+'_long.png'
                            img_d_rot.save(img_d_rot_path,'PNG')
                            label_long_temp = Image.fromarray(label_long[:,:,i])
                            label_rot_long = np.array(label_long_temp.rotate(angle=i*60, fillcolor=255))
                            label_long_path =label_save_dir+'cy_'+'num_'+str(floder_id)+'_yaw_'+str(int(i*60)) \
                                                        +'_ap_'+str(int(ap_ind))+'_pitch_'+str(int(pt)) \
                                                        +'_roll_'+str(int(rt))+'_fl_'+str(int(fl_ind))+ '_long.png'
                            #label_rot_long.save(label_long_path,'PNG')
                            cv2.imwrite(label_long_path,label_rot_long.reshape((image_pixel_after,image_pixel_after)))

                            grasp_paras = np.zeros(5).reshape(1,1,5)
                            grasp_paras[0][0][0]=ap_ind
                            grasp_paras[0][0][1]=i * 60
                            grasp_paras[0][0][2]=pt
                            grasp_paras[0][0][3]=rt
                            grasp_paras[0][0][4]=fl_ind
                            grasp_paras_save_path = sec_input_dir+'cy_'+'num_'+str(floder_id)+'_yaw_'+str(int(i*60)) \
                                                        +'_ap_'+str(int(ap_ind))+'_pitch_'+str(int(pt)) \
                                                        +'_roll_'+str(int(rt))+'_fl_'+str(int(fl_ind))+'_long.npy'
                            np.save(grasp_paras_save_path, grasp_paras.astype(np.int))

    p.disconnect()
    gc.collect()
if __name__ == '__main__':
#    print(time.localtime(time.time()))items

    with concurrent.futures.ProcessPoolExecutor() as executor:

        futures = [executor.submit(custom_method_saveimg,floder_id) for floder_id in range(example_number_need_collect)]
        for future in concurrent.futures.as_completed(futures):
             try:
                 print(future.result())
             except Exception as exc:
                 print(f'Generated an exception: {exc}')
