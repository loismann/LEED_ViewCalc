# First we have to import some stuff to make python understand
# what it's working with:

import Rhino
import Rhino.Geometry as rg
import Grasshopper.DataTree as DataTree
import clr

clr.AddReference("Grasshopper")
from Grasshopper.Kernel.Data import GH_Path
import Rhino.Geometry.Intersect as rgi
from decimal import Decimal
import ghpythonlib.parallel
import System
import os
import datetime
import time

# Print the Start time
print datetime.datetime.now().time()

# Maybe server busy fix?
# Turns off the Server Busy message in Rhino
Rhino.Runtime.HostUtils.DisplayOleAlerts(False)

# Make sure the "desired_rotation_angle" value from the GH component gives us ray counts
# that are divisibly by 360 (in whole-degree increments)
divisibilitylist = []
for i in range(1, 360):
    if (360 % i) == 0:
        divisibilitylist.append(i)

# found out how to round the desired "desired_rotation_angle" value to the closest number
# actually divisibly by 360 here:
# https://stackoverflow.com/questions/12141150/from-list-of-integers-get-number-closest-to-a-given-value
rotationangle = min(divisibilitylist, key=lambda x: abs(x - desired_rotation_angle))
print "Each view caculation will be " + str(rotationangle) + " degrees apart"
radian_conversion = 57.2958


def calculate_intersections(POINT):
    point = POINT

    collected_wall_intersections = []
    collected_window_intersections = []

    # these are going to get placeholder values in the first section, and then the correct values will replaced
    # in the second section
    final_wall_intersections = []
    final_window_intersections = []

    ray = rg.Ray3d(point, rg.Vector3d.YAxis)

    for j in range(0, int(360 / rotationangle)):
        wall_intersection = rgi.Intersection.RayShoot(ray, walls, 1)
        window_intersection = rgi.Intersection.RayShoot(ray, windows, 1)
        # print wall_intersection
        if wall_intersection:
            for pt in wall_intersection:
                collected_wall_intersections.append(pt)
                final_wall_intersections.append(None)
        else:
            collected_wall_intersections.append("False")

        if window_intersection:
            for pt in window_intersection:
                collected_window_intersections.append(pt)
                final_window_intersections.append(None)
        else:
            collected_window_intersections.append("False")

        direction = ray.Direction
        direction.Rotate((rotationangle / radian_conversion), rg.Vector3d.ZAxis)
        ray = rg.Ray3d(point, direction)

    final_wall_intersections = []
    final_window_intersections = []

    for j in range(0, len(collected_window_intersections)):
        window_value = collected_window_intersections[j]
        wall_value = collected_wall_intersections[j]

        # if a given ray (rotation angle) finds a wall intersection and a window intersection
        # it means one of two things:
        # Either the window and wall are in the same plane
        # Or the wall is in front of the window.

        # if there is a wall intersection and no window intersection: add the wall intersection to the final list
        if wall_value != "False" and window_value == "False":
            final_wall_intersections.append(wall_value)

        # if there is a window intersection and no wall intersectionL add the window intersection to the final list
        elif window_value != "False" and wall_value == "False":
            final_window_intersections.append(window_value)

        # if there are both window and wall intersections:
        # Find out which one is closest to the origin point and then add that point to the correct final list
        elif window_value != "False" and wall_value != "False":
            window_intersect_distance = round(Decimal(rg.Point3d.DistanceTo(point, window_value)), 3)
            wall_intersect_distance = round(Decimal(rg.Point3d.DistanceTo(point, wall_value)), 3)

            if window_intersect_distance < wall_intersect_distance:
                final_window_intersections.append(window_value)
            elif wall_intersect_distance < window_intersect_distance:
                final_wall_intersections.append(wall_value)
            elif wall_intersect_distance == window_intersect_distance:
                final_window_intersections.append(window_value)

    return [final_window_intersections, final_wall_intersections]


def calculate_angles(ANALYSIS_POINT, WINDOW_POINTS, WALL_POINTS):
    vectors = []
    pass_fail = "Red"
    # print "length of list 'window points':" + len(WINDOW_POINTS)
    for pt in WINDOW_POINTS:
        vect = rg.Vector3d(pt - ANALYSIS_POINT)
        vectors.append(vect)

    for i in range(0, len(vectors)):
        angles = []
        study_vector = vectors[i]
        for j in range(0, len(vectors)):
            if j < len(vectors) - 1:
                # print str(i) + " less than"
                # measure the angle between i and i+1
                angle = int((rg.Vector3d.VectorAngle(study_vector, vectors[j + 1], rg.Plane.WorldXY)) * 57.2958)
                angles.append(angle)

            elif j == len(vectors) - 1:
                # print str(i) + " == "
                # if i is the last number in the lst, measure it against the first number (i)
                angle = int((rg.Vector3d.VectorAngle(study_vector, vectors[j - 1], rg.Plane.WorldXY)) * 57.2958)
                angles.append(angle)

        for angle in angles:
            # print angle
            if angle >= 90 and angle <= 180:
                # print "yay!"
                pass_fail = "Green"

        # print WINDOW_POINTS
        # print WALL_POINTS
    return [pass_fail, ANALYSIS_POINT]


T_WallPts = DataTree[rg.Point3d]()
T_WindowPts = DataTree[rg.Point3d]()
T_OriginPts = DataTree[rg.Point3d]()
T_PassFailVals = DataTree[str]()
T_PassFailPct = DataTree[str]()
# counter = 0

# These are all the files we'll be creating
WallPts_completeName = os.path.join(File_Path, "WallPts" + ".txt")
WindowPts_completeName = os.path.join(File_Path, "WindowPts" + ".txt")
OriginPts_completeName = os.path.join(File_Path, "OriginPts" + ".txt")
PassFailVals_completeName = os.path.join(File_Path, "PassFailVals" + ".txt")
PassFailPct_completeName = os.path.join(File_Path, "PassFailPct" + ".txt")
RoomName_CompleteName = os.path.join(File_Path, "RoomName" + ".txt")
log_fName = os.path.join(File_Path, "Log" + ".txt")

class pointID(object):
    def __init__(self, point, ID, srfID):
        self.ID = ID
        self.point = point
        self.srfID = srfID


def parallel_calc(point):
    try:
        index = point.ID
        srfID = point.srfID
        # print index
        myPath = GH_Path(srfID, index)
        results = calculate_intersections(point.point)
        T_WallPts.AddRange(results[0], myPath)
        T_WindowPts.AddRange(results[1], myPath)
        results2 = calculate_angles(point.point, results[0], results[1])
        T_OriginPts.Add(results2[1], myPath)
        # THIS IS THE PART THAT UPDATES THE PROGRESS METER IN THE RHINO DISPLAY.  CHANGE THE
        # % VALUE TO ADD MORE UPDATE STEPS.  PROCESSING PENALTIES APPLY

        T_PassFailVals.Add(results2[0], myPath)

    except Exception as e:
        print e.message

def write_intersect_points():
    WallPointsFileObject = open(WallPts_completeName, "a")
    WindowPtsFileObject = open(WindowPts_completeName, "a")
    if T_WallPts.BranchCount == T_WindowPts.BranchCount:
        for i in range(T_WallPts.BranchCount):
            try:
                windowData = "Branch:" + str(T_WindowPts.Paths[i]) + "\n"
                wallData = windowData
            except:
                windowData = "Branch:ERROR\n"
                wallData = "Branch:ERROR\n"
            maxvalue = max([len(T_WallPts.Branches[i]), len(T_WindowPts.Branches[i])])
            for j in range(maxvalue):
                try:
                    if j < len(T_WallPts.Branches[i]):
                        wallData += "%s\n" % T_WallPts.Branches[i][j]
                except:
                    wallData += "ERROR\n"
                try:
                    if j < len(T_WindowPts.Branches[i]):
                        windowData += "%s\n" % T_WindowPts.Branches[i][j]
                except:
                    windowData += "ERROR\n"
            WallPointsFileObject.write(wallData)
            WindowPtsFileObject.write(windowData)

    else: # iterate through each tree separately.
        # Write out the Wall Points
        for i in range(T_WallPts.BranchCount):
            wallData = "Branch:" + str(T_WallPts.Paths[i]) + "\n"
            for j in range(len(T_WallPts.Branches[i])):
                try:
                    if j < len(T_WallPts.Branches[i]):
                        wallData += "%s\n" % T_WallPts.Branches[i][j]
                except:
                    wallData += "ERROR\n"
            WallPointsFileObject.write(wallData)
        # Write out the Window Points
        for i in range(T_WindowPts.BranchCount):
            windowData = "Branch:" + str(T_WindowPts.Paths[i]) + "\n"
            for j in range(len(T_WindowPts.Branches[i])):
                try:
                    if j < len(T_WindowPts.Branches[i]):
                        windowData += "%s\n" % T_WindowPts.Branches[i][j]
                except:
                    windowData += "ERROR\n"
            WindowPtsFileObject.write(windowData)

    WallPointsFileObject.close()
    WindowPtsFileObject.close()

def write_roomnames():

    RoomNameFileObject = open(RoomName_CompleteName, "a")
    for i in range(Room_Names.BranchCount):
        branchData = "Branch:" + str(Room_Names.Paths[i]) + "\n"
        RoomNameFileObject.write(branchData)
        for j in range(len(Room_Names.Branches[i])):
            roomName = "%s\n" % Room_Names.Branches[i][j]
            RoomNameFileObject.write(roomName)



def write_originpass_file():
    # Write out the values that will only be one item per tree
    origPtData = ""
    passFailData = ""
    OriginPtsFileObject = open(OriginPts_completeName, "a")
    PassFailValsFileObject = open(PassFailVals_completeName, "a")
    if T_OriginPts.BranchCount == T_PassFailVals:
        for i in range(T_OriginPts.BranchCount):
            # Write to data file each 100 branches
            if i % 100 == 0:
                OriginPtsFileObject.write(origPtData)
                PassFailValsFileObject.write(passFailData)
                origPtData = ""
                passFailData = ""

            origPtData += "Branch:" + str(T_OriginPts.Paths[i]) + "\n"
            passFailData += "Branch:" + str(T_PassFailVals.Paths[i]) + "\n"

            for j in range(len(T_OriginPts.Branches[i])):
                try:
                    origPtData += "%s\n" % T_OriginPts.Branches[i][j]
                    passFailData += "%s\n" % T_PassFailVals.Branches[i][j]
                except:
                    origPtData += "ERROR\n"
                    passFailData += "ERROR\n"
        # write remaining data...
        OriginPtsFileObject.write(origPtData)
        PassFailValsFileObject.write(passFailData)

    else: # Branches don't align properly between origin and pass fail
        for i in range(T_OriginPts.BranchCount):
            # Write to data file each 100 branches
            if i % 100 == 0:
                OriginPtsFileObject.write(origPtData)
                origPtData = ""
            origPtData += "Branch:" + str(T_OriginPts.Paths[i]) + "\n"
            for j in range(len(T_OriginPts.Branches[i])):
                try:
                    origPtData += "%s\n" % T_OriginPts.Branches[i][j]
                except:
                    origPtData += "ERROR\n"
        for i in range(T_PassFailVals.BranchCount):
            # Write to data file each 100 branches
            if i % 100 == 0:
                PassFailValsFileObject.write(passFailData)
                passFailData = ""
            passFailData += "Branch:" + str(T_PassFailVals.Paths[i]) + "\n"
            for j in range(len(T_OriginPts.Branches[i])):
                try:
                    passFailData += "%s\n" % T_PassFailVals.Branches[i][j]
                except:
                    passFailData += "ERROR\n"

        # write remaining data...
        OriginPtsFileObject.write(origPtData)
        PassFailValsFileObject.write(passFailData)

    OriginPtsFileObject.close()
    PassFailValsFileObject.close()

def write_percent_file():
    # Calculate the pass fail percentages

    PassFailPctFileObject = open(PassFailPct_completeName, "a")
    for i in range(T_PassFailVals.BranchCount):
        path = T_PassFailVals.Paths[i]
        pctData = ""
        srf_index = path.Indices[0]
        TotalNumberPointsEvaluated = 0
        NumPassVals = 0
        NumFailVals = 0

        for j in range(len(T_PassFailVals.Branches[i])):
            TotalNumberPointsEvaluated += 1
            if T_PassFailVals.Branches[i][j] == "Red":
                NumFailVals += 1
            if T_PassFailVals.Branches[i][j] == "Green":
                NumPassVals += 1

        Percent_Pass = NumPassVals / TotalNumberPointsEvaluated
        Percent_Fail = NumFailVals / TotalNumberPointsEvaluated
        pctData += "Branch: {" + str(srf_index) + "}\n"
        pctData += "Percent Pass:" + str(Percent_Pass * 100) + "%\n"
        pctData += "Percent Fail:" + str(Percent_Fail * 100) + "%\n"

        PassFailPctFileObject.write(pctData)

    PassFailPctFileObject.close()

if parallel:
    log = ""
    print "Parallel Computation: Enabled"
    log += "Parallel Computation: Enabled\n"
    print "Checking Directory for Existing Files:"
    log += "Checking Directory for Existing Files:" + str(datetime.datetime.now().time()) + "\n"
    # Check for pre-existing files and remove them

    RemovedFiles = []

    if RemoveFiles:
        if os.path.isfile(WallPts_completeName):
            #WallPointsFileObject = open(WallPts_completeName, "a")
            #WallPointsFileObject.close()
            os.remove(WallPts_completeName)
            RemovedFiles.append("...Removed WallPoints File")
            log += "...Removed WallPoints File\n"
        if os.path.isfile(RoomName_CompleteName):
            os.remove(RoomName_CompleteName)
            RemovedFiles.append("...Removed RoomNames File")
            log += "...Removed Room Names Files\n"
        if os.path.isfile(WindowPts_completeName):
            #WindowPtsFileObject = open(WindowPts_completeName, "a")
            #WindowPtsFileObject.close()
            os.remove(WindowPts_completeName)
            RemovedFiles.append("...Removed WindowPoints File")
            log += "...Removed WindowPoints File\n"
        if os.path.isfile(OriginPts_completeName):
            os.remove(OriginPts_completeName)
            RemovedFiles.append("...Removed OriginPoints File")
            log += "...Removed OriginPts File\n"
        if os.path.isfile(PassFailVals_completeName):
            os.remove(PassFailVals_completeName)
            RemovedFiles.append("...Removed Pass/Fail Values File")
            log += "...Removed Pass/Fail Values File\n"
        if os.path.isfile(PassFailPct_completeName):
            os.remove(PassFailPct_completeName)
            RemovedFiles.append("...Removed Pass/Fail Percentages File")
            log += "...Removed Pass/Fail Percentage File\n"
        if os.path.isfile(log_fName):
            os.remove(log_fName)
            RemovedFiles.append("...Removed Log File")
            log += "...Removed Log File\n"
        else:
            RemovedFiles.append("No Files Found To Remove")
            log += "...No Files Found to Remove.\n"
    #

    log += "Starting Process (" + str(datetime.datetime.now().time()) + ")...\n"

    upper_limit = points.BranchCount
    Rhino.UI.StatusBar.ShowProgressMeter(0, upper_limit, "View Calc Progress", True, True)

    # Create and open files for all the differnt categories
    for i in range(points.BranchCount):
        ID_List = []
        T_WallPts.Clear()
        T_WindowPts.Clear()
        T_OriginPts.Clear()
        T_PassFailVals.Clear()
        T_PassFailPct.Clear()
        for j, point in enumerate(points.Branches[i]):
            ID_List.append(pointID(point, j, i))

        ghpythonlib.parallel.run(parallel_calc, ID_List, False)
        write_intersect_points()
        write_originpass_file()
        write_percent_file()
        Rhino.UI.StatusBar.UpdateProgressMeter(i + 1, True)
    log += "Complete (" + str(datetime.datetime.now().time()) + ")...\n"
    #log += "Calling Parallel Function (" + str(datetime.datetime.now().time()) + ")...\n"
    # Run the calc - this appends to the open files

    Rhino.UI.StatusBar.HideProgressMeter()


    """
            =======================================
            
            Write All of the Window and Wall Points
    
            =======================================
    """
    #log += "Converting Window and Wall Points to String (" + str(datetime.datetime.now().time()) + ")...\n"
    #log += "Converting Origin Points and Pass/Fail to String (" + str(datetime.datetime.now().time()) + ")...\n"
    #log += "Calculating Percentages (" + str(datetime.datetime.now().time()) + ")...\n"
    # PassFailPctFileObject.write("Branch: {" + str(srf_index) + "}\n")
    # PassFailPctFileObject.write("Percent Pass:" + str(Percent_Pass*100) + "%\n")
    # PassFailPctFileObject.write("Percent Fail:" + str(Percent_Fail*100) + "%\n")

    # time.sleep(2)
    #log += "Writing Wall Points (" + str(datetime.datetime.now().time()) + ")...\n"
    #log += "Writing Window Points (" + str(datetime.datetime.now().time()) + ")...\n"
    #log += "Writing Origin Points (" + str(datetime.datetime.now().time()) + ")...\n"
    #log += "Writing Pass/Fail (" + str(datetime.datetime.now().time()) + ")...\n"
    #log += "Writing Percentages (" + str(datetime.datetime.now().time()) + ")...\n"

    log_file = open(log_fName, "a")
    log_file.write(log)
    log_file.close()


    """
    #Close all files
    WallPointsFileObject.close()
    WindowPtsFileObject.close()
    OriginPtsFileObject.close()
    PassFailValsFileObject.close()
    PassFailPctFileObject.close()
    """

# Print the End time
# Write out the room names
# write_roomnames()

print datetime.datetime.now().time()
