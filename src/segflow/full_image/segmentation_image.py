import numpy as np
from skimage.segmentation import expand_labels
from skimage.morphology import binary_dilation, binary_erosion, disk
from scipy.ndimage import binary_erosion as nd_binary_erosion
from skimage.measure import regionprops
from tqdm import tqdm
import hashlib
import cv2

from scipy.ndimage import distance_transform_edt
from scipy.ndimage import binary_dilation, generate_binary_structure

import numpy as np
from scipy.ndimage import distance_transform_edt
from skimage.segmentation import expand_labels

from scipy.ndimage import minimum_filter, maximum_filter

from skimage.segmentation import expand_labels


class SegmentationImage(np.ndarray):
    def __new__(cls, input_array):
        """
        Create a new SegmentationImage instance, inheriting from numpy.ndarray.

        Parameters:
        - input_array: numpy array, the input data for the single channel.
        """
        if not isinstance(input_array, np.ndarray):
            raise TypeError("Input must be a numpy array")
        if input_array.ndim != 2:
            raise ValueError("Input must be a 2D numpy array")
        if not (np.issubdtype(input_array.dtype, np.integer) or input_array.dtype == np.bool_):
            raise TypeError("Input array must have integer or boolean data type")

        # Cast the input_array to our new class (SegmentationImage)
        obj = np.asarray(input_array).view(cls)
        obj._centroids_cache = None
        obj._area_cache = None
        obj._MinorAxisLength_cache = None
        obj._MajorAxisLength_cache = None
        obj._Extent_cache = None
        obj._Solidity_cache = None
        obj._Eccentricity_cache = None
        obj._Orientation_cache = None
        obj._segment_patches_cache = None
        obj._checksum = obj._calculate_checksum()
        return obj

    def __init__(self, input_array):
        """
        Initialize any extra attributes or logic.
        Since numpy array creation happens in __new__, __init__ is mostly used for
        initializing any non-array attributes.
        """
        pass  # We are not adding any extra attributes at this point

    def _initialize_attributes(self, source_image):
        """
        Copy attributes from the source image to the new instance.
        """
        # Set any attributes from source_image here
        pass

    def _calculate_checksum(self):
        """
        Calculate a checksum for the current state of the array to track modifications.
        """
        return hashlib.md5(np.ascontiguousarray(self.view(np.ndarray))).hexdigest()

    def _invalidate_cache(self):
        """
        Invalidate the cached centroids if the array has been modified.
        """
        self._centroids_cache = None
        self._area_cache = None
        self._MinorAxisLength_cache = None
        self._MajorAxisLength_cache = None
        self._Extent_cache = None
        self._Solidity_cache = None
        self._Eccentricity_cache = None
        self._Orientation_cache = None

    def __setitem__(self, key, value):
        """
        Override __setitem__ to invalidate cache when the array is modified.
        """
        super(SegmentationImage, self).__setitem__(key, value)
        self._invalidate_cache()

    @property
    def centroids(self):
        if self._centroids_cache is None:
            self._calculate_centroids()
        return self._centroids_cache

    @property
    def area(self):
        if self._area_cache is None:
            self._calculate_area()
        return self._area_cache

    @property
    def MinorAxisLength(self):
        if self._MinorAxisLength_cache is None:
            self._calculate_MinorAxisLength()
        return self._MinorAxisLength_cache

    @property
    def MajorAxisLength(self):
        if self._MajorAxisLength_cache is None:
            self._calculate_MajorAxisLength()
        return self._MajorAxisLength_cache

    @property
    def Extent(self):
        if self._Extent_cache is None:
            self._calculate_Extent()
        return self._Extent_cache

    @property
    def Solidity(self):
        if self._Solidity_cache is None:
            self._calculate_Solidity()
        return self._Solidity_cache

    @property
    def Eccentricity(self):
        if self._Eccentricity_cache is None:
            self._calculate_Eccentricity()
        return self._Eccentricity_cache

    @property
    def Orientation(self):
        if self._Orientation_cache is None:
            self._calculate_Orientation()
        return self._Orientation_cache

    def has_missing_cells(self):
        """
        Check if any labels in the SegmentationImage have no associated pixels.

        Returns:
        - bool: True if any labels are missing (i.e., have no pixels), otherwise False.
        """
        # Get all unique labels in the segmentation image
        labels = np.unique(self)
        
        # Check each label (except for background label 0) for missing pixels
        for label in labels:
            if label == 0:
                continue  # Skip the background label
            if np.sum(self == label) == 0:
                return True  # Missing cell found

        return False  # No missing cells

    def randomize_segmentation(self, seed=1):
        """
        Randomize cell labels in the segmentation mask for better visualization.

        Parameters:
        - seed: Random seed for reproducibility.
        
        Returns:
        - SegmentationImage instance with randomized labels.
        """
        # Identify unique non-zero labels
        unique_labels = np.unique(self)
        non_zero_labels = unique_labels[unique_labels > 0]

        # Create a random permutation of the non-zero labels
        rng = np.random.default_rng(seed=seed)
        randomized_labels = rng.permutation(len(non_zero_labels)) + 1  # Start labels from 1

        # Create a mapping that retains zero (background)
        label_mapping = np.zeros(unique_labels.max() + 1, dtype=np.int32)
        label_mapping[non_zero_labels] = randomized_labels

        # Apply the mapping to the segmentation image
        new_image = self.copy()
        new_image = label_mapping[self]
        

        new_instance = self.__class__(new_image)
        new_instance._initialize_attributes(self)
        return new_instance

    def dilate_segmentation2(self, dilation_pixels=1):
        """
        Dilate each non-zero label in the segmentation image by a specified number of pixels.

        Parameters:
        - dilation_pixels: Number of pixels to dilate each label.

        Returns:
        - SegmentationImage instance with dilated labels.
        """
        if dilation_pixels < 1:
            raise ValueError("dilation_pixels must be at least 1")

        new_image = self.copy()
        if self.dtype == np.bool_ or np.array_equal(np.unique(self), [0, 1]):
            # Binary segmentation
            print("dilating a binary segmentation")
            selem = disk(dilation_pixels)
            dilated = binary_dilation(self, selem)
            new_image = dilated.astype(self.dtype)
        else:
            print("dilating a label segmentation")
            # Labeled segmentation
            # Use expand_labels from skimage.segmentation
            dilated = expand_labels(self, distance=dilation_pixels)
            new_image = dilated.astype(self.dtype)
        
        new_instance = self.__class__(new_image)
       	new_instance._initialize_attributes(self)
       	return new_instance

    def erode_segmentation2(self, erosion_pixels=1):
        """
        Erode each non-zero label in the segmentation image by a specified number of pixels.

        Parameters:
        - erosion_pixels: Number of pixels to erode each label.

        Returns:
        - SegmentationImage instance with eroded labels.
        """
        if erosion_pixels < 1:
            raise ValueError("erosion_pixels must be at least 1")

        new_image = self.copy()
        if self.dtype == np.bool_ or np.array_equal(np.unique(self), [0, 1]):
            # Binary segmentation
            selem = disk(erosion_pixels)
            eroded = binary_erosion(self, selem)
            new_image = eroded.astype(self.dtype)
        else:
            # Labeled segmentation
            # Erode each label individually to prevent label merging
            labels = np.unique(self)
            labels = labels[labels != 0]  # Exclude background
            eroded = np.zeros_like(self)
            selem = disk(erosion_pixels)
            for label in labels:
                mask = self == label
                eroded_mask = nd_binary_erosion(mask, structure=selem)
                eroded[eroded_mask] = label
            new_image = eroded.astype(self.dtype)

        new_instance = self.__class__(new_image)
       	new_instance._initialize_attributes(self)
       	return new_instance  

    def _calculate_centroids(self):
        """
        Calculate the centroid of each labeled region in the segmentation image along with additional metadata.
        Zero-labeled regions (background) are excluded.

        Returns:
        - A dictionary where keys are labels (excluding zero) and values are the centroid coordinate,
        """
        # Check if cached centroids are valid
        current_checksum = self._calculate_checksum()
        if (
            self._centroids_cache is not None and
            current_checksum == self._checksum
        ):
            return self._centroids_cache


        centroids = {}
        regions = regionprops(self)

        for region in tqdm(regions, desc="Calculating Centroids", unit="region"):
            if region.label != 0:
                centroid_y, centroid_x = region.centroid  # Centroid is in (y, x) format
                centroid_y = int(round(centroid_y))
                centroid_x = int(round(centroid_x))


                # Store metadata
                centroids[region.label] = (centroid_y, centroid_x)

        # Cache the centroids and update the checksum and bbox_size
        self._centroids_cache = centroids
        self._checksum = current_checksum

        return centroids

    def _calculate_area(self):
        """
        Calculate the pixel area of each labeled region in the segmentation image along with additional metadata.
        Zero-labeled regions (background) are excluded.

        Returns:
        - A dictionary where keys are labels (excluding zero) and values are the area,
        """
        # Check if cached areas are valid
        current_checksum = self._calculate_checksum()
        if (
            self._area_cache is not None and
            current_checksum == self._checksum
        ):
            return self._area_cache


        area = {}
        regions = regionprops(self)

        for region in tqdm(regions, desc="Calculating Area", unit="region"):
            if region.label != 0:
                # sum the number of pixels with the current label to get the area
                curr_area = np.sum(labeled_image == label)

                # Store metadata
                area[region.label] = curr_area

        # Cache the area and update the checksum and bbox_size
        self._area_cache = area
        self._checksum = current_checksum

        return area

    def _calculate_MajorAxisLength(self):
        """
        Calculate the MajorAxisLength of each labeled region in the segmentation image along with additional metadata.
        Zero-labeled regions (background) are excluded.

        Returns:
        - A dictionary where keys are labels (excluding zero) and values are the MajorAxisLength,
        """
        # Check if cached MajorAxisLengths are valid
        current_checksum = self._calculate_checksum()
        if (
            self._MajorAxisLength_cache is not None and
            current_checksum == self._checksum
        ):
            return self._MajorAxisLength_cache


        MajorAxisLength = {}
        regions = regionprops(self)

        for region in tqdm(regions, desc="Calculating MajorAxisLength", unit="region"):
            if region.label != 0:
                # Get the major_axis_length property
                curr_MajorAxisLength = region.major_axis_length

                # Store metadata
                MajorAxisLength[region.label] = curr_MajorAxisLength

        # Cache the MajorAxisLength and update the checksum and bbox_size
        self._MajorAxisLength_cache = MajorAxisLength
        self._checksum = current_checksum

        return MajorAxisLength

    def _calculate_MinorAxisLength(self):
        """
        Calculate the MinorAxisLength of each labeled region in the segmentation image along with additional metadata.
        Zero-labeled regions (background) are excluded.

        Returns:
        - A dictionary where keys are labels (excluding zero) and values are the MinorAxisLength,
        """
        # Check if cached MinorAxisLengths are valid
        current_checksum = self._calculate_checksum()
        if (
            self._MinorAxisLength_cache is not None and
            current_checksum == self._checksum
        ):
            return self._MinorAxisLength_cache


        MinorAxisLength = {}
        regions = regionprops(self)

        for region in tqdm(regions, desc="Calculating MinorAxisLength", unit="region"):
            if region.label != 0:
                # Get the minor_axis_length property
                curr_MinorAxisLength = region.minor_axis_length

                # Store metadata
                MinorAxisLength[region.label] = curr_MinorAxisLength

        # Cache the MinorAxisLength and update the checksum and bbox_size
        self._MinorAxisLength_cache = MinorAxisLength
        self._checksum = current_checksum

        return MinorAxisLength

    def _calculate_Eccentricity(self):
        """
        Calculate the Eccentricity of each labeled region in the segmentation image along with additional metadata.
        Zero-labeled regions (background) are excluded.

        Returns:
        - A dictionary where keys are labels (excluding zero) and values are the Eccentricity,
        """
        # Check if cached Eccentricities are valid
        current_checksum = self._calculate_checksum()
        if (
            self._Eccentricity_cache is not None and
            current_checksum == self._checksum
        ):
            return self._Eccentricity_cache


        Eccentricity = {}
        regions = regionprops(self)

        for region in tqdm(regions, desc="Calculating Eccentricity", unit="region"):
            if region.label != 0:
                # Get the eccentricity property
                curr_Eccentricity = region.eccentricity

                # Store metadata
                Eccentricity[region.label] = curr_Eccentricity

        # Cache the Eccentricity and update the checksum and bbox_size
        self._Eccentricity_cache = Eccentricity
        self._checksum = current_checksum

        return Eccentricity

    def _calculate_Solidity(self):
        """
        Calculate the Solidity of each labeled region in the segmentation image along with additional metadata.
        Zero-labeled regions (background) are excluded.

        Returns:
        - A dictionary where keys are labels (excluding zero) and values are the Solidity,
        """
        # Check if cached Solidities are valid
        current_checksum = self._calculate_checksum()
        if (
            self._Solidity_cache is not None and
            current_checksum == self._checksum
        ):
            return self._Solidity_cache


        Solidity = {}
        regions = regionprops(self)

        for region in tqdm(regions, desc="Calculating Solidity", unit="region"):
            if region.label != 0:
                # Get the solidity property
                curr_Solidity = region.solidity

                # Store metadata
                Solidity[region.label] = curr_Solidity

        # Cache the Solidity and update the checksum and bbox_size
        self._Solidity_cache = Solidity
        self._checksum = current_checksum

        return Solidity

    def _calculate_Extent(self):
        """
        Calculate the Extent of each labeled region in the segmentation image along with additional metadata.
        Zero-labeled regions (background) are excluded.

        Returns:
        - A dictionary where keys are labels (excluding zero) and values are the Extent,
        """
        # Check if cached Extents are valid
        current_checksum = self._calculate_checksum()
        if (
            self._Extent_cache is not None and
            current_checksum == self._checksum
        ):
            return self._Extent_cache


        Extent = {}
        regions = regionprops(self)

        for region in tqdm(regions, desc="Calculating Extent", unit="region"):
            if region.label != 0:
                # Get the extent property
                curr_Extent = region.extent

                # Store metadata
                Extent[region.label] = curr_Extent

        # Cache the Extent and update the checksum and bbox_size
        self._Extent_cache = Extent
        self._checksum = current_checksum

        return Extent

    def _calculate_Orientation(self):
        """
        Calculate the Orientation of each labeled region in the segmentation image along with additional metadata.
        Zero-labeled regions (background) are excluded.

        Returns:
        - A dictionary where keys are labels (excluding zero) and values are the Orientation,
        """
        # Check if cached Orientations are valid
        current_checksum = self._calculate_checksum()
        if (
            self._Orientation_cache is not None and
            current_checksum == self._checksum
        ):
            return self._Orientation_cache


        Orientation = {}
        regions = regionprops(self)

        for region in tqdm(regions, desc="Calculating Orientation", unit="region"):
            if region.label != 0:
                # Get the orientation property
                curr_Orientation = region.orientation

                # Store metadata
                Orientation[region.label] = curr_Orientation

        # Cache the Orientation and update the checksum and bbox_size
        self._Orientation_cache = Orientation
        self._checksum = current_checksum

        return Orientation

    def apply_binary_mask(self, binary_mask, method):
        """
        Apply a binary mask to the segmentation image.

        Parameters:
        - binary_mask: SegmentationImage, the binary mask where 0 = false and > 0 = true.
        - method: str, one of {'centroid_overlap', 'all_in', 'any_in'} to define the masking behavior.

        Returns:
        - A new SegmentationImage instance with the mask applied.
        """
        if not isinstance(binary_mask, SegmentationImage):
            raise TypeError("binary_mask must be a SegmentationImage instance.")
        
        # Treat the binary mask where > 0 is True and 0 is False.
        if not np.array_equal(np.unique(binary_mask), [0, 1]) and not np.issubdtype(binary_mask.dtype, np.bool_):
            warn("Binary mask contains values other than 0 and 1. Treating all non-zero values as True.")
        
        # Convert binary mask to boolean
        binary_mask_bool = binary_mask > 0
        new_image = self.copy()
        
        if method == 'centroid_overlap':
            # Get the centroids of the labeled regions in segmentation_image
            centroids = self.centroids
            if centroids is None:
                raise ValueError("centroid_overlap requires execution of calculate_centroids() prior to applying the mask.")
            # Convert centroid coordinates to integer indices for lookup
            centroids_in_false_areas = [
                label for label, centroid in centroids.items()
                if not binary_mask_bool[int(centroid[0]), int(centroid[1])]
            ]
            
            # Set the regions with centroids in false areas to zero
            mask = np.isin(self, centroids_in_false_areas)
            new_image[mask] = 0
            
        elif method == 'all_in':
            # Use logical indexing to find labels in the False area
            labels_in_false_area = np.unique(self[~binary_mask_bool])
            # Zero out corresponding labels
            mask = np.isin(self, labels_in_false_area)
            new_image[mask] = 0

        elif method == 'any_in':
            # Get all labels that appear in the True areas of the binary mask
            labels_in_true_area = np.unique(self[binary_mask_bool])
            all_labels = np.unique(self)
            # Labels to zero are those not in labels_in_true_area and not background (0)
            labels_to_zero = np.setdiff1d(all_labels, labels_in_true_area)
            # Zero out those labels
            mask = np.isin(self, labels_to_zero)
            new_image[mask] = 0
                    
        else:
            raise ValueError(f"Invalid method '{method}'. Choose from 'centroid_overlap', 'all_in', 'any_in'.")
        
        new_instance = self.__class__(new_image)
        new_instance._initialize_attributes(self)
        return new_instance




    def dilate_segmentation4(self, dilation_pixels=1):
        """
        Dilate each non-zero label in the segmentation image by a specified number of pixels.

        Parameters:
        - dilation_pixels: Number of pixels to dilate each label.

        Returns:
        - SegmentationImage instance with dilated labels.
        """
        if dilation_pixels < 1:
            raise ValueError("dilation_pixels must be at least 1")

        if self.dtype == np.bool_ or np.array_equal(np.unique(self), [0, 1]):
            # Binary segmentation
            dilated = binary_dilation_fast(self, dilation_pixels)
            new_image = dilated.astype(self.dtype)
        else:
            # Labeled segmentation
            dilated = dilate_labels(self, dilation_pixels)
            new_image = dilated.astype(self.dtype)

    
        new_instance = self.__class__(new_image)
        new_instance._initialize_attributes(self)
        return new_instance

    def erode_segmentation4(self, erosion_pixels=1):
        """
        Erode each non-zero label in the segmentation image by a specified number of pixels.

        Parameters:
        - erosion_pixels: Number of pixels to erode each label.

        Returns:
        - SegmentationImage instance with eroded labels.
        """
        if erosion_pixels < 1:
            raise ValueError("erosion_pixels must be at least 1")

        if self.dtype == np.bool_ or np.array_equal(np.unique(self), [0, 1]):
            # Binary segmentation
            eroded = binary_erosion_fast(self, erosion_pixels)
            new_image = eroded.astype(self.dtype)
        else:
            # Labeled segmentation
            eroded = erode_labels(self, erosion_pixels)
            new_image = eroded.astype(self.dtype)

        new_instance = self.__class__(new_image)
        new_instance._initialize_attributes(self)
        return new_instance

    def dilate_segmentation3(self, dilation_pixels=1):
        """
        Dilate each non-zero label in the segmentation image by a specified number of pixels.

        Parameters:
        - dilation_pixels: Number of pixels to dilate each label.

        Returns:
        - SegmentationImage instance with dilated labels.
        """
        if dilation_pixels < 1:
            raise ValueError("dilation_pixels must be at least 1")

        if self.dtype == np.bool_ or np.array_equal(np.unique(self), [0, 1]):
            # Binary segmentation
            dilated = binary_dilation_fast(self, dilation_pixels)
            new_image = dilated.astype(self.dtype)
        else:
            # Labeled segmentation
            # Use expand_labels from skimage.segmentation
            from skimage.segmentation import expand_labels
            dilated = expand_labels(self, distance=dilation_pixels)
            new_image = dilated.astype(self.dtype)
        
        new_instance = self.__class__(new_image)
        new_instance._initialize_attributes(self)
        return new_instance

    def erode_segmentation3(self, erosion_pixels=1):
        """
        Erode each non-zero label in the segmentation image by a specified number of pixels.

        Parameters:
        - erosion_pixels: Number of pixels to erode each label.

        Returns:
        - SegmentationImage instance with eroded labels.
        """
        if erosion_pixels < 1:
            raise ValueError("erosion_pixels must be at least 1")

        if self.dtype == np.bool_ or np.array_equal(np.unique(self), [0, 1]):
            # Binary segmentation
            eroded = binary_erosion_fast(self, erosion_pixels)
            new_image = eroded.astype(self.dtype)
        else:
            # Labeled segmentation
            # Erode each label individually to prevent label merging
            labels = np.unique(self)
            labels = labels[labels != 0]  # Exclude background
            eroded = np.zeros_like(self)
            for label in labels:
                mask = self == label
                eroded_mask = binary_erosion_fast(mask, erosion_pixels)
                eroded[eroded_mask] = label
            new_image = eroded.astype(self.dtype)

        new_instance = self.__class__(new_image)
        new_instance._initialize_attributes(self)
        return new_instance

    def close_segmentation(self, closing_pixels=1):
        """
        Fill small holes in the segmentation image by performing morphological closing.

        Parameters:
        - closing_pixels: Number of pixels to close.

        Returns:
        - SegmentationImage instance with closed areas.
        """
        if closing_pixels < 1:
            raise ValueError("closing_pixels must be at least 1")

        if self.dtype == np.bool_ or np.array_equal(np.unique(self), [0, 1]):
            # Binary segmentation
            image_uint8 = (self.astype(np.uint8) * 255)
            closed = morphological_closing_fast(image_uint8, closing_pixels)
            new_image = (closed > 0).astype(self.dtype)
        else:
            # For labeled images, you might need a different approach
            # because morphological closing can merge labels.
            # You can process each label individually if needed.
            pass  # Implement as required

        new_instance = self.__class__(new_image)
        new_instance._initialize_attributes(self)
        return new_instance

    def dilate_segmentation(self, dilation_pixels=1):
        """
        Dilate each non-zero label in the segmentation image by a specified number of pixels.

        Parameters:
        - dilation_pixels: Number of pixels to dilate each label.

        Returns:
        - SegmentationImage instance with dilated labels.
        """
        if dilation_pixels < 1:
            raise ValueError("dilation_pixels must be at least 1")

        if self.dtype == np.bool_ or np.array_equal(np.unique(self), [0, 1]):
            # Binary segmentation
            # Convert boolean image to uint8 format expected by OpenCV
            image_uint8 = (self.astype(np.uint8) * 255)
            dilated = binary_dilation_fast(image_uint8, dilation_pixels)
            # Convert back to original format
            new_image = (dilated > 0).astype(self.dtype)
        else:
            # Labeled segmentation
            # Use expand_labels from skimage.segmentation
            from skimage.segmentation import expand_labels
            dilated = expand_labels(self, distance=dilation_pixels)
            new_image = dilated.astype(self.dtype)
        
        new_instance = self.__class__(new_image)
        new_instance._initialize_attributes(self)
        return new_instance

    def erode_segmentation(self, erosion_pixels=1):
        """
        Erode each non-zero label in the segmentation image by a specified number of pixels.

        Parameters:
        - erosion_pixels: Number of pixels to erode each label.

        Returns:
        - SegmentationImage instance with eroded labels.
        """
        if erosion_pixels < 1:
            raise ValueError("erosion_pixels must be at least 1")

        if self.dtype == np.bool_ or np.array_equal(np.unique(self), [0, 1]):
            # Binary segmentation
            # Convert boolean image to uint8 format expected by OpenCV
            image_uint8 = (self.astype(np.uint8) * 255)
            eroded = binary_erosion_fast(image_uint8, erosion_pixels)
            # Convert back to original format
            new_image = (eroded > 0).astype(self.dtype)
        else:
            # Labeled segmentation
            # Erode each label individually to prevent label merging
            labels = np.unique(self)
            labels = labels[labels != 0]  # Exclude background
            eroded = np.zeros_like(self)
            for label in labels:
                mask = (self == label).astype(np.uint8) * 255
                eroded_mask = binary_erosion_fast(mask, erosion_pixels)
                eroded[eroded_mask > 0] = label
            new_image = eroded.astype(self.dtype)

        new_instance = self.__class__(new_image)
        new_instance._initialize_attributes(self)
        return new_instance


def morphological_closing_fast(image, closing_radius):
    """
    Perform morphological closing using OpenCV with a circular structuring element.

    Parameters:
    - image: Binary input image (numpy array of type uint8 with values 0 or 255).
    - closing_radius: Radius of the structuring element.

    Returns:
    - Image after morphological closing.
    """
    kernel_size = 2 * closing_radius + 1
    selem = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))

    closed_image = cv2.morphologyEx(
        image, cv2.MORPH_CLOSE, selem, borderType=cv2.BORDER_REPLICATE
    )

    return closed_image



def binary_dilation_fast(image, dilation_radius):
    """
    Perform binary dilation using OpenCV with a circular structuring element.

    Parameters:
    - image: Binary input image (numpy array of type uint8 with values 0 or 255).
    - dilation_radius: Radius of the structuring element.

    Returns:
    - Dilated binary image.
    """
    # Create a circular structuring element
    kernel_size = 2 * dilation_radius + 1
    selem = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))

    # Perform dilation
    dilated_image = cv2.dilate(image, selem, iterations=1)

    return dilated_image

def binary_erosion_fast(image, erosion_radius):
    """
    Perform binary erosion using OpenCV with a circular structuring element.

    Parameters:
    - image: Binary input image (numpy array of type uint8 with values 0 or 255).
    - erosion_radius: Radius of the structuring element.

    Returns:
    - Eroded binary image.
    """
    # Create a circular structuring element
    kernel_size = 2 * erosion_radius + 1
    selem = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))

    # Perform erosion
    eroded_image = cv2.erode(image, selem, iterations=1)

    return eroded_image


def binary_dilation_fast3(image, dilation_radius):
    """
    Perform binary dilation on a large binary image efficiently.

    Parameters:
    - image: Binary input image (boolean or 0/1).
    - dilation_radius: Number of pixels to dilate.

    Returns:
    - Dilated binary image.
    """
    # Use a square structuring element with size based on the dilation radius
    size = 2 * dilation_radius + 1
    # Perform the dilation using maximum_filter
    dilated_image = maximum_filter(image, size=size, mode='constant')
    return dilated_image.astype(image.dtype)


def binary_erosion_fast3(image, erosion_radius):
    """
    Perform binary erosion on a large binary image efficiently.

    Parameters:
    - image: Binary input image (boolean or 0/1).
    - erosion_radius: Number of pixels to erode.

    Returns:
    - Eroded binary image.
    """
    # Use a square structuring element with size based on the erosion radius
    size = 2 * erosion_radius + 1
    # Perform the erosion using minimum_filter
    eroded_image = minimum_filter(image, size=size, mode='constant')
    return eroded_image.astype(image.dtype)



def dilate_labels4(labels, dilation_radius):
    """
    Dilate labeled image efficiently using distance transform.

    Parameters:
    - labels: Input labeled image (numpy array).
    - dilation_radius: Radius for dilation (number of pixels).

    Returns:
    - Dilated labeled image.
    """
    # Expand the labeled regions using the expand_labels function
    dilated_labels = expand_labels(labels, distance=dilation_radius)
    return dilated_labels

