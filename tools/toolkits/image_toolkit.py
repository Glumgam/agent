"""
IMAGE Toolkit
自動生成・統合ツール集。
カテゴリ: image
作成日: 2026-03-31
収録ツール:
- tool_opencv_reconstruct_3d: Deep Research により獲得。分野: AI 論文
"""
from pathlib import Path


# ==================================================
# tool_opencv_reconstruct_3d
# ==================================================

def tool_opencv_reconstruct_3d(image1_path, image2_path, camera_matrix1, camera_matrix2, dist_coeffs1, dist_coeffs2):
    try:
        # Load images
        img1 = cv2.imread(image1_path)
        img2 = cv2.imread(image2_path)

        if img1 is None or img2 is None:
            return "ERROR: Image not found."

        # Convert to grayscale
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

        # Detect features (SIFT)
        sift = cv2.SIFT_create()
        keypoints1, descriptors1 = sift.detectAndCompute(gray1, None)
        keypoints2, descriptors2 = sift.detectAndCompute(gray2, None)

        if not keypoints1 or not keypoints2:
            return "ERROR: No keypoints found."

        # Match features (BFMatcher)
        bf = cv2.BFMatcher()
        matches = bf.knnMatch(descriptors1, descriptors2, k=2)

        good_matches = []
        for m, n in matches:
            if m.distance < 0.75 * n.distance:
                good_matches.append(m)

        # Extract matched points
        src_pts = [keypoints1[m.queryIdx].pt for m in good_matches]
        dst_pts = [keypoints2[m.trainIdx].pt for m in good_matches]

        src_pts = np.float32(src_pts)
        dst_pts = np.float32(dst_pts)

        # Estimate fundamental matrix
        F, mask = cv2.findFundamentalMat(src_pts, dst_pts, cv2.FM_RANSAC)  # Added missing closing parenthesis

        if F is None:
            return "ERROR: Fundamental matrix not found."

        # Essential matrix from camera matrices and fundamental matrix
        E = np.dot(camera_matrix1.T, np.dot(F, camera_matrix2))

        # Recover pose (camera 1 to camera 2)
        _, R, t, _ = cv2.recoverPose(E, src_pts[mask.ravel() == 1], dst_pts[mask.ravel() == 1], camera_matrix2)

        # Triangulate points
        P1 = np.hstack((np.eye(3), np.zeros((3, 1))))  # Camera 1 projection matrix (identity)
        P2 = np.hstack((R, t))  # Camera 2 projection matrix

        # Triangulate points using the projection matrices
        points_4d_homogeneous = cv2.triangulatePoints(P1, P2, src_pts.T, dst_pts.T)
        points_3d = points_4d_homogeneous[:3] / points_4d_homogeneous[3]

        return points_3d

    except Exception as e:
        return f"ERROR: {str(e)}"
