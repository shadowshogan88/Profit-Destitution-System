/*
Author       : Dreamguys
Template Name: POS - Bootstrap Admin Template
*/


$(document).ready(function(){

	// Variables declarations
	var $wrapper = $('.main-wrapper');
	var $slimScrolls = $('.slimscroll');
	var $pageWrapper = $('.page-wrapper');

	// Page Content Height Resize
	$(window).resize(function () {
		if ($('.page-wrapper').length > 0) {
			var height = $(window).height();
			$(".page-wrapper").css("min-height", height);
		}
	});

	// Mobile menu sidebar overlay
	$('body').append('<div class="sidebar-overlay"></div>');


	$(document).on('click', '#mobile_btn', function() {
		$wrapper.toggleClass('slide-nav');
		$('.sidebar-overlay').toggleClass('opened');
		$('html').addClass('menu-opened');
		$('#task_window').removeClass('opened');
		return false;
	});

	$(".sidebar-overlay").on("click", function () {
		$('html').removeClass('menu-opened');
		$(this).removeClass('opened');
		$wrapper.removeClass('slide-nav');
		$('.sidebar-overlay').removeClass('opened');
		$('#task_window').removeClass('opened');
	});

	// Table Responsive
	setTimeout(function () {
		$(document).ready(function () {
			$('.table').parent().addClass('table-responsive');
		});
	}, 1000);

	
	// Datatable
	if($('.datatable').length > 0) {
		$('.datatable').DataTable({
			"bFilter": true,
			"sDom": 'fBtlpi',  
			"ordering": true,
			"language": {
				search: ' ',
				sLengthMenu: '_MENU_',
				searchPlaceholder: "Search",
				sLengthMenu: ' _MENU_ Rows per page',
				info: "_START_ - _END_ ",
				paginate: {
					next: ' <i class="icon-chevron-right"></i>',
					previous: '<i class="icon-chevron-left"></i>'
				},
			 },
			initComplete: (settings, json)=>{
				$('.dt-search').appendTo('#tableSearch');
				$('.dt-search').appendTo('.search-input');

			},	
		});
	}

	// Datetimepicker
	if($('.datetimepicker').length > 0 ){
		$('.datetimepicker').datetimepicker({
			format: 'DD-MM-YYYY',
			icons: {
				up: "fas fa-angle-up",
				down: "fas fa-angle-down",
				next: 'fas fa-angle-right',
				previous: 'fas fa-angle-left'
			}
		});
	}

	// Sidebar
	var Sidemenu = function() {
		this.$menuItem = $('.sidebar-menu a');
	};

	function init() {
		var $this = Sidemenu;
		$('.sidebar-menu a').on('click', function(e) {
			if($(this).parent().hasClass('submenu')) {
				e.preventDefault();
			}
			if(!$(this).hasClass('subdrop')) {
				$('ul', $(this).parents('ul:first')).slideUp(250);
				$('a', $(this).parents('ul:first')).removeClass('subdrop');
				$(this).next('ul').slideDown(350);
				$(this).addClass('subdrop');
			} else if($(this).hasClass('subdrop')) {
				$(this).removeClass('subdrop');
				$(this).next('ul').slideUp(350);
			}
		});
		$('.sidebar-menu ul li.submenu a.active').parents('li:last').children('a:first').addClass('active').trigger('click');
	}

	// Sidebar
	var Colsidemenu = function() {
		this.$menuItems = $('.sidebar-right a');
	};

	function colinit() {
    var $this = Colsidemenu;

    // Unbind previous click handlers to avoid duplicates
		$('.sidebar-right ul a').off('click').on('click', function (e) {

			// Check if parent has 'submenu' class
			if ($(this).parent().hasClass('submenu')) {
				e.preventDefault();
				console.log("1");
			}

			// If this is not currently expanded
			if (!$(this).hasClass('subdrop')) {
				// Close all sibling submenus
				$(this).closest('ul').find('ul').slideUp(250);
				$(this).closest('ul').find('a').removeClass('subdrop');

				// Open the clicked submenu
				$(this).next('ul').slideDown(350);
				$(this).addClass('subdrop');
				console.log("0");

			} else { // If already expanded, collapse it
				$(this).removeClass('subdrop');
				$(this).next('ul').slideUp(350);
				console.log("3");
			}
		});

		// Open submenu if an active item is inside
		$('.sidebar-right ul li.submenu a.active').parents('li').children('a').addClass('active subdrop');
		$('.sidebar-right ul li.submenu a.active').parents('ul').slideDown(350);
	}

	colinit();

	// Sidebar Initiate
	init();
	$(document).on('mouseover', function(e) {
        e.stopPropagation();
        if ($('body').hasClass('mini-sidebar') && $('#toggle_btn').is(':visible')) {
            var targ = $(e.target).closest('.sidebar, .header-left').length;
            if (targ) {
                $('body').addClass('expand-menu');
                $('.subdrop + ul').slideDown();
            } else {
                $('body').removeClass('expand-menu');
                $('.subdrop + ul').slideUp();
            }
            return false;
        }
		if ($('body').hasClass('mini-sidebar')) {
            var targ = $(e.target).closest('.sidebar, .header-left').length;
            if (targ) {
                $('body.layout-box-mode').addClass('expand-menu');
                $('.subdrop + ul').slideDown();
            } else {
                $('body').removeClass('expand-menu');
                $('.subdrop + ul').slideUp();
            }
            return false;
        }
    });
		
	// Tooltip
	if($('[data-bs-toggle="tooltip"]').length > 0) {
		var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
		var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
			return new bootstrap.Tooltip(tooltipTriggerEl)
		})
	}

	// Date Range Picker
	if ($('.daterangepick').length > 0) {
		const start = moment().subtract(29, "days");
		const end = moment();
		const report_range = (start, end) => {
			$(".daterangepick span").html(`${start.format("D MMM YY")} - ${end.format("D MMM YY")}`);
		};
		$(".daterangepick").daterangepicker(
			{
				startDate: start,
				endDate: end,
				ranges: {
					'Today': [moment(), moment()],
					'Yesterday': [moment().subtract(1, "days"), moment().subtract(1, "days")],
					"Last 7 Days": [moment().subtract(6, "days"), moment()],
					"Last 30 Days": [moment().subtract(29, "days"), moment()],
					"This Month": [moment().startOf("month"), moment().endOf("month")],
					"Last Month": [
						moment().subtract(1, "month").startOf("month"),
						moment().subtract(1, "month").endOf("month")
					]
				}
			},
			report_range
		);
		report_range(start, end);
	}

	// Initialize Flatpickr on elements with data-provider="flatpickr"
	document.querySelectorAll('[data-provider="flatpickr"]').forEach(el => {
		const config = {
			disableMobile: true
		};
		if (el.hasAttribute('data-date-format')) {
			config.dateFormat = el.getAttribute('data-date-format');
		}
		if (el.hasAttribute('data-enable-time')) {
			config.enableTime = true;
			config.dateFormat = config.dateFormat ? `${config.dateFormat} H:i` : 'Y-m-d H:i';
		}
		if (el.hasAttribute('data-altFormat')) {
			config.altInput = true;
			config.altFormat = el.getAttribute('data-altFormat');
		}
		if (el.hasAttribute('data-minDate')) {
			config.minDate = el.getAttribute('data-minDate');
		}
		if (el.hasAttribute('data-maxDate')) {
			config.maxDate = el.getAttribute('data-maxDate');
		}
		if (el.hasAttribute('data-default-date')) {
			const defaultDate = el.getAttribute('data-default-date');
			// Check if it's a valid date string
			if (!["true", "false", "", null].includes(defaultDate) && !isNaN(Date.parse(defaultDate))) {
				config.defaultDate = defaultDate;
			}
		}
		if (el.hasAttribute('data-multiple-date')) {
			config.mode = 'multiple';
		}
		if (el.hasAttribute('data-range-date')) {
			config.mode = 'range';
		}
		if (el.hasAttribute('data-inline-date')) {
			config.inline = true;
			const inlineDate = el.getAttribute('data-inline-date');
			if (!["true", "false", "", null].includes(inlineDate) && !isNaN(Date.parse(inlineDate))) {
				config.defaultDate = inlineDate;
			}
		}
		if (el.hasAttribute('data-disable-date')) {
			config.disable = el.getAttribute('data-disable-date').split(',');
		}
		if (el.hasAttribute('data-week-number')) {
			config.weekNumbers = true;
		}
		flatpickr(el, config);
	});

	// Select Table Checkbox
	$('#select-all').on('change', function () {
		$('.form-check.form-check-md input[type="checkbox"]').prop('checked', this.checked);
	});

	if ($('.toggle-password').length > 0) {
		$(document).on('click', '.toggle-password', function () {
			const $icon = $(this).find('i');
			const $input = $(this).closest('.input-group').find('.pass-input');
			if ($input.attr('type') === 'password') {
				$input.attr('type', 'text');
				$icon.removeClass('icon-eye-off').addClass('icon-eye');
			} else {
				$input.attr('type', 'password');
				$icon.removeClass('icon-eye').addClass('icon-eye-off');
			}
		});
	}

	// header fixed
	$(window).on("scroll", function () {
		var scrollTop = $(this).scrollTop();
		var triggerHeight = 50; // add class after 50px scroll
	  
		if (scrollTop > triggerHeight) {
		  $(".navbar-header").addClass("fixed");
		} else {
		  $(".navbar-header").removeClass("fixed");
		}
	});

	// Services Slider
	$('.services-slider').each(function () {
		const $slider = $(this);
		if (!$slider.hasClass('slick-initialized')) {
			$slider.slick({
				dots: false,
				infinite: true,
				speed: 2000,
				slidesToShow: 4,
				slidesToScroll: 1,
				autoplay: false,
				arrows: true,
				prevArrow: $('.category-prev'),
				nextArrow: $('.category-next'),
				responsive: [
					{
						breakpoint: 1400,
						settings: { slidesToShow: 3, slidesToScroll: 1 }
					},
					{
						breakpoint: 992,
						settings: { slidesToShow: 3, slidesToScroll: 1 }
					},
					{
						breakpoint: 768,
						settings: { slidesToShow: 2, slidesToScroll: 1 }
					},
					{
						breakpoint: 576,
						settings: { slidesToShow: 1, slidesToScroll: 1 }
					}
				]
			});
		}
	});

	// Category Slider
	$('.category-slider').each(function () {
		const $slider = $(this);
		if (!$slider.hasClass('slick-initialized')) {
			$slider.slick({
				dots: false,
				infinite: true,
				speed: 2000,
				slidesToShow: 4,
				slidesToScroll: 1,
				autoplay: false,
				arrows: true,
				prevArrow: $('.category-prev'),
				nextArrow: $('.category-next'),
				responsive: [
					{
						breakpoint: 1400,
						settings: { slidesToShow: 4, slidesToScroll: 1 }
					},
					{
						breakpoint: 1199,
						settings: { slidesToShow: 3, slidesToScroll: 1 }
					},
					{
						breakpoint: 768,
						settings: { slidesToShow: 2, slidesToScroll: 1 }
					},
					{
						breakpoint: 576,
						settings: { slidesToShow: 1, slidesToScroll: 1 }
					}
				]
			});
		}
	});

	// Category Slider
	$('.link-item-slider').each(function () {
		const $slider = $(this);
		if (!$slider.hasClass('slick-initialized')) {
			$slider.slick({
				dots: false,
				infinite: true,
				speed: 2000,
				slidesToShow: 4,
				slidesToScroll: 1,
				autoplay: false,
				arrows: true,
				prevArrow: $('.category-prev'),
				nextArrow: $('.category-next'),
				responsive: [
					{
						breakpoint: 1400,
						settings: { slidesToShow: 3, slidesToScroll: 1 }
					},
					{
						breakpoint: 1199,
						settings: { slidesToShow: 3, slidesToScroll: 1 }
					},
					{
						breakpoint: 768,
						settings: { slidesToShow: 2, slidesToScroll: 1 }
					},
					{
						breakpoint: 576,
						settings: { slidesToShow: 1, slidesToScroll: 1 }
					}
				]
			});
		}
	});
	

	$(document).ready(function() {
        if ($('.select-multiple').length > 0) { // Check if element exists to avoid errors
            $('.select-multiple').select2({
                placeholder: "Select options",
                allowClear: true,
                width: '100%' // Ensures it fills your .pos-card container
            });
        }
    });

	// Select 2 Search
	if ($('.select2').length > 0) {
		$('.select2').select2({
			minimumResultsForSearch: 0, 
			width: '100%'
		});
	}

	// Select 2
	if ($('.select').length > 0) {
		$('.select').select2({
			minimumResultsForSearch: -1,
			width: '100%'
		});
	}

	// Click Active
	document.querySelectorAll('.plan-card').forEach(card => {
		card.addEventListener('click', () => {
		  document.querySelectorAll('.plan-card')
			.forEach(c => c.classList.remove('active'));
		  card.classList.add('active');
		});
	});

	// Time Picker
	document.querySelectorAll('[data-provider="timepickr"]').forEach(item => {
		const attrs = item.attributes;
		const config = {
			enableTime: true,
			noCalendar: true,
			dateFormat: "H:i"
		};

		if (attrs["data-time-hrs"]) {
			config.time_24hr = true;
		}

		if (attrs["data-min-time"]) {
			config.minTime = attrs["data-min-time"].value;
		}

		if (attrs["data-max-time"]) {
			config.maxTime = attrs["data-max-time"].value;
		}

		if (attrs["data-default-time"]) {
			config.defaultDate = attrs["data-default-time"].value;
		}

		if (attrs["data-time-inline"]) {
			config.inline = true;
			config.defaultDate = attrs["data-time-inline"].value;
		}

		flatpickr(item, config);
	});

	// Show menu option
	$(document).ready(function() {
		// Show Menu Logic
		$('.menu-option-show').on('click', function() {
			// Find the menu-option inside the same .pos-right parent
			$(this).closest('.pos-right').find('.menu-option').slideDown(400);
		});
	
		// Hide Menu Logic
		$('.hide-menu-option').on('click', function() {
			// Find the menu-option inside the same .pos-right parent
			$(this).closest('.pos-right').find('.menu-option').slideUp(400);
		});
	});

	// Product card select
	$(document).ready(function() {
		// Click event for the product card
		$('.pos-card').on('click', function() {
			$(this).toggleClass('active');
		});
	
		// Prevent quantity controls from triggering the "active" border
		$('.quantity-control').on('click', function(e) {
			e.stopPropagation();
		});
	
		// Optional: Basic Quantity Plus/Minus functionality
		$('.add-btn').on('click', function() {
			let $input = $(this).siblings('.quantity-input');
			$input.val(parseInt($input.val()) + 1);
		});
	
		$('.minus-btn').on('click', function() {
			let $input = $(this).siblings('.quantity-input');
			let val = parseInt($input.val());
			if (val > 0) {
				$input.val(val - 1);
			}
		});
	});

	// Service Active
	$(document).on('click', '.services-card', function() {
		$('.services-card').not(this).removeClass('active');
		$(this).toggleClass('active');
	});

});


